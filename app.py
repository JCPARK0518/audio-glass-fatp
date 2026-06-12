import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import tempfile
import os
from matplotlib import colors as mcolors

st.set_page_config(page_title="Audio Glass FATP DATA 분석", layout="wide")
st.title("📊 Audio Glass FATP DATA 분석")

# 파일명 + 크기로 캐시 키 생성
@st.cache_data
def load_and_process_file(file_bytes, file_name, file_size):
    """파일명과 크기로 캐싱"""
    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    
    df = pd.read_excel(tmp_path)
    os.unlink(tmp_path)
    
    df = df[~df.iloc[:, 0].isin(['UpperLimit', 'LowerLimit'])].reset_index(drop=True)
    
    # 항목 감지 (최적화)
    items = []
    cols = list(df.columns)
    
    for i in range(len(cols) - 2):
        col_str = str(cols[i])
        next_col_str = str(cols[i + 1])
        after_col_str = str(cols[i + 2])
        
        if not next_col_str.startswith('[') or not next_col_str.endswith(']IsPass'):
            continue
        
        if next_col_str != f"[{col_str}]IsPass":
            continue
        
        try:
            float(after_col_str)
            items.append({'name': col_str, 'idx': i})
        except ValueError:
            pass
    
    sn_list = sorted(df['SN'].dropna().unique().tolist())
    
    return df, items, sn_list

# 세로축 범위 설정
@st.cache_data
def get_ylim(item_name):
    item_lower = item_name.lower()
    
    if 'seal' in item_lower and 'mic' in item_lower and 'fr' in item_lower:
        return None
    
    if 'mic' in item_lower and 'fr' in item_lower:
        return (-100, 0)
    
    return None

# 파일 업로드
uploaded_files = st.file_uploader("엑셀 파일 업로드 (여러 개 가능)", type=["xlsx"], accept_multiple_files=True)

if uploaded_files:
    if 'files_data_cache' not in st.session_state:
        st.session_state.files_data_cache = {}
    
    if 'last_files' not in st.session_state:
        st.session_state.last_files = []
    
    # 파일 변경 감지 (새로운 파일만 로드)
    current_file_names = [f.name for f in uploaded_files]
    if current_file_names != st.session_state.last_files:
        files_data = {}
        cache_status = st.status("파일 로딩 중...", expanded=True)
        
        for idx, uploaded_file in enumerate(uploaded_files):
            cache_key = f"{uploaded_file.name}_{uploaded_file.size}"
            
            if cache_key in st.session_state.files_data_cache:
                files_data[uploaded_file.name] = st.session_state.files_data_cache[cache_key]
                with cache_status:
                    st.write(f"✅ {uploaded_file.name} (캐시)")
            else:
                try:
                    with cache_status:
                        file_bytes = uploaded_file.getbuffer()
                        df, items, sn_list = load_and_process_file(file_bytes, uploaded_file.name, uploaded_file.size)
                        
                        st.session_state.files_data_cache[cache_key] = {
                            'df': df,
                            'items': items,
                            'sn_list': sn_list
                        }
                        
                        files_data[uploaded_file.name] = st.session_state.files_data_cache[cache_key]
                        st.write(f"✅ {uploaded_file.name}")
                except Exception as e:
                    with cache_status:
                        st.error(f"❌ {uploaded_file.name}: {str(e)}")
        
        cache_status.update(label="✅ 완료", state="complete")
        st.session_state.last_files = current_file_names
        st.session_state.files_data = files_data
    else:
        files_data = st.session_state.files_data
    
    if files_data:
        # 파일 정보
        info_cols = st.columns(min(len(files_data), 4))
        for col, (file_name, data) in zip(info_cols, files_data.items()):
            with col:
                st.metric(
                    file_name.split('.')[0],
                    f"{len(data['items'])}항목",
                    f"{len(data['sn_list'])}SN"
                )
        
        # 선택 UI - 한 줄에 모두 표시 (빠른 업데이트)
        st.subheader("📋 비교 항목 선택")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            file_list = list(files_data.keys())
            if 'selected_file_idx' not in st.session_state:
                st.session_state.selected_file_idx = 0
            
            file_idx = st.selectbox(
                "파일",
                range(len(file_list)),
                format_func=lambda x: file_list[x].split('.')[0],
                key="file_idx"
            )
            st.session_state.selected_file_idx = file_idx
            selected_file = file_list[file_idx]
        
        with col2:
            items_list = [x['name'] for x in files_data[selected_file]['items']]
            if 'selected_item_idx' not in st.session_state:
                st.session_state.selected_item_idx = 0
            
            item_idx = st.selectbox(
                "항목",
                range(len(items_list)),
                format_func=lambda x: items_list[x][:50],
                key="item_idx"
            )
            st.session_state.selected_item_idx = item_idx
            selected_item = items_list[item_idx]
        
        with col3:
            sn_search = st.text_input("SN 검색", key="sn_search", placeholder="검색어 입력")
            sn_list_current = files_data[selected_file]['sn_list']
            
            if sn_search:
                search_lower = sn_search.lower()
                filtered_sn = [sn for sn in sn_list_current if search_lower in sn.lower()]
                if filtered_sn:
                    selected_sn = st.selectbox(f"검색 ({len(filtered_sn)})", filtered_sn, key="sn_select", index=0)
                else:
                    selected_sn = None
            else:
                selected_sn = st.selectbox(f"SN ({len(sn_list_current)})", sn_list_current, key="sn_select", index=0)
        
        # 비교 목록
        if 'comparison_list' not in st.session_state:
            st.session_state.comparison_list = []
        
        col_add, col_clear = st.columns(2)
        with col_add:
            if st.button("➕ 추가", use_container_width=True):
                if selected_sn is None:
                    st.warning("SN을 선택하세요")
                else:
                    new_item = {
                        'file': selected_file,
                        'item': selected_item,
                        'sn': selected_sn,
                        'label': f"{selected_file.split('.')[0]} - {selected_item[:30]} ({selected_sn})"
                    }
                    if new_item not in st.session_state.comparison_list:
                        st.session_state.comparison_list.append(new_item)
                        st.toast("✅ 추가", icon="✅")
        
        with col_clear:
            if st.button("🗑️ 초기화", use_container_width=True):
                st.session_state.comparison_list = []
                st.toast("초기화됨", icon="🗑️")
        
        # 비교 목록 표시
        if st.session_state.comparison_list:
            st.subheader(f"📊 비교 목록 ({len(st.session_state.comparison_list)}개)")
            
            cols = st.columns(2)
            for idx, item in enumerate(st.session_state.comparison_list):
                with cols[idx % 2]:
                    col_info, col_delete = st.columns([4, 1])
                    with col_info:
                        st.write(f"**{idx+1}.** {item['label']}")
                    with col_delete:
                        if st.button("❌", key=f"delete_{idx}", use_container_width=True):
                            st.session_state.comparison_list.pop(idx)
                            st.rerun()
            
            # 그래프
            if st.button("📈 그래프 생성", type="primary", use_container_width=True):
                fig, ax = plt.subplots(figsize=(14, 7))
                color_list = list(mcolors.TABLEAU_COLORS.values())
                ylim_to_apply = None
                plot_count = 0
                
                for plot_idx, comp_item in enumerate(st.session_state.comparison_list):
                    file_name = comp_item['file']
                    item_name = comp_item['item']
                    sn = comp_item['sn']
                    label = comp_item['label']
                    
                    df = files_data[file_name]['df']
                    items = files_data[file_name]['items']
                    
                    item_idx = None
                    for itm in items:
                        if itm['name'] == item_name:
                            item_idx = itm['idx']
                            break
                    
                    if item_idx is None:
                        continue
                    
                    sn_rows = df[df['SN'] == sn]
                    if len(sn_rows) == 0:
                        continue
                    
                    row_idx = sn_rows.index[0]
                    sweep_data_cols = []
                    for i in range(item_idx + 2, len(df.columns)):
                        try:
                            float(df.columns[i])
                            sweep_data_cols.append(i)
                        except:
                            break
                    
                    if not sweep_data_cols:
                        continue
                    
                    freqs, values = [], []
                    for col_idx in sweep_data_cols:
                        try:
                            freq = float(df.columns[col_idx])
                            value = float(df.iloc[row_idx, col_idx])
                            if not np.isnan(value):
                                freqs.append(freq)
                                values.append(value)
                        except:
                            continue
                    
                    if freqs:
                        color = color_list[plot_idx % len(color_list)]
                        ax.plot(freqs, values, marker='o', label=label, linewidth=2.5, markersize=5, color=color)
                        plot_count += 1
                    
                    if plot_idx == 0:
                        ylim_to_apply = get_ylim(item_name)
                
                ax.set_xscale('log')
                ax.set_xlabel('Frequency (Hz)', fontsize=12, fontweight='bold')
                ax.set_ylabel('Value (dB)', fontsize=12, fontweight='bold')
                first_item = st.session_state.comparison_list[0]['item'] if st.session_state.comparison_list else ''
                ax.set_title(f'{first_item}', fontsize=14, fontweight='bold')
                
                if ylim_to_apply is not None:
                    ax.set_ylim(ylim_to_apply)
                
                ax.legend(fontsize=10, loc='best')
                ax.grid(True, alpha=0.3)
                
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)
                
                if plot_count > 0:
                    st.success(f"✅ {plot_count}개 그래프 생성 완료")
        else:
            st.info("항목을 선택 후 '➕ 추가' 버튼을 클릭하세요")
