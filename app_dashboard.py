import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="제주 세일즈 분석 대시보드", layout="wide")

# 사이드바 스타일링
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        min-width: 300px;
        max-width: 300px;
    }
    .insight-card {
        background-color: #f0f8ff;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #4CAF50;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 분석 보고서 로드 함수
def load_markdown_report(file_path):
    """마크다운 보고서 로드"""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                return f.read()
    return None

import glob
import re

# 공통 도구: 문자열에서 첫 번째 숫자 추출 (콤마 제거 포함)
def extract_numeric_value(val):
    if isinstance(val, str):
        # 콤마 제거 후 첫 번째 연속된 숫자 뭉치 찾기
        match = re.search(r'(\d+)', val.replace(',', ''))
        return float(match.group(1)) if match else 0.0
    return float(val) if val is not None else 0.0

# 데이터 로드 환경 설정
def get_latest_data_path():
    # 1. 버전 파일 검색
    files = glob.glob('data/preprocessed_data_*.csv')
    versioned_files = []
    for f in files:
        match = re.search(r'preprocessed_data_(\d+)\.csv', f)
        if match:
             versioned_files.append((f, int(match.group(1))))
    
    if versioned_files:
        # 버전순 정렬 후 최신 파일 반환
        versioned_files.sort(key=lambda x: x[1])
        return versioned_files[-1][0]
    
    # 2. 기본 파일 검색
    if os.path.exists('data/preprocessed_data.csv'):
        return 'data/preprocessed_data.csv'
    return None

DATA_PATH = get_latest_data_path()

@st.cache_data
def load_data(path):
    if path and os.path.exists(path):
        try:
            df = pd.read_csv(path, encoding='utf-8-sig')
        except:
            df = pd.read_csv(path, encoding='cp949')
        
        # 금액 데이터 처리
        def clean_money(val):
            if isinstance(val, str):
                return float(val.replace(',', ''))
            return val
        
        df['실결제 금액'] = df['실결제 금액'].apply(clean_money)
        df['공급단가'] = df['공급단가'].apply(clean_money)
        df['주문-취소 수량'] = pd.to_numeric(df['주문-취소 수량'], errors='coerce').fillna(0)
        df['주문수량'] = pd.to_numeric(df['주문수량'], errors='coerce').fillna(0)
        df['취소수량'] = pd.to_numeric(df['취소수량'], errors='coerce').fillna(0)
        
        # 날짜 처리
        df['주문일'] = pd.to_datetime(df['주문일'])
        df['주문일자'] = df['주문일'].dt.date
        
        # 문자열 컬럼 결측치 및 타입 처리 (정렬 에러 방지)
        df['셀러명'] = df['셀러명'].fillna('미지정').astype(str)
        df['품종'] = df['품종'].fillna('기타').astype(str)
        
        return df
    return None

@st.cache_data
def load_visit_data():
    # 최신 버전(salesvisit_1.csv) 우선 로드
    path = 'data/salesvisit_1.csv'
    if os.path.exists(path):
        try:
            v_df = pd.read_csv(path, encoding='utf-8-sig')
            v_df['일자'] = pd.to_datetime(v_df['일자']).dt.date
            return v_df
        except:
            return None
    return None

@st.cache_data
def load_click_data():
    # 최신 버전(salesclick_1.csv) 우선 로드
    path = 'data/salesclick_1.csv'
    if not os.path.exists(path):
        path = 'data/salesclick.csv'
        
    if os.path.exists(path):
        try:
            c_df = pd.read_csv(path, encoding='utf-8-sig')
            return c_df
        except:
            return None
    return None

df = load_data(DATA_PATH)
visit_df = load_visit_data()
click_df = load_click_data()

# 캐시/데이터 확인용 메시지 (개발용)
if df is not None:
    if '이벤트 여부' in df.columns:
        st.toast(f"데이터 로드 성공: {os.path.basename(DATA_PATH)} (이벤트 컬럼 포함)")
    else:
        st.toast(f"데이터 로드 성공: {os.path.basename(DATA_PATH)} (이벤트 컬럼 없음!)", icon="⚠️")

if df is not None:
    st.title("🍊 제주 세일즈 데이터 분석 대시보드")
    
    # 사이드바 필터
    st.sidebar.header("🔍 검색 필터")
    
    # 기간 필터
    min_date = df['주문일자'].min()
    max_date = df['주문일자'].max()
    date_range = st.sidebar.date_input("분석 기간", [min_date, max_date], min_value=min_date, max_value=max_date)
    
    # Top 10 셀러 및 품종 계산 (매출 기준)
    top10_sellers = df.groupby('셀러명')['실결제 금액'].sum().nlargest(10).index.tolist()
    top10_varieties = df.groupby('품종')['실결제 금액'].sum().nlargest(10).index.tolist()
    
    # 필터용 컬럼 생성
    df['셀러명_필터'] = df['셀러명'].apply(lambda x: x if x in top10_sellers else '기타 (Top 10 외)')
    df['품종_필터'] = df['품종'].apply(lambda x: x if x in top10_varieties else '기타 (Top 10 외)')
    
    # 셀러 및 품종 필터 (옵션: Top 10 + 기타)
    seller_options = sorted(top10_sellers) + ['기타 (Top 10 외)']
    variety_options = sorted(top10_varieties) + ['기타 (Top 10 외)']
    
    sellers = st.sidebar.multiselect("셀러 선택 (매출 상위 10 + 기타)", options=seller_options, default=[])
    varieties = st.sidebar.multiselect("품종 선택 (매출 상위 10 + 기타)", options=variety_options, default=[])
    
    # 데이터 필터링 적용
    mask = (df['주문일자'] >= date_range[0]) & (df['주문일자'] <= date_range[1])
    if sellers:
        mask &= df['셀러명_필터'].isin(sellers)
    if varieties:
        mask &= df['품종_필터'].isin(varieties)
    
    filtered_df = df[mask].copy()
    
    # [Refactor] 이익 및 이익률 전역 계산 (중복 제거)
    if not filtered_df.empty:
        filtered_df['단위공급단가'] = filtered_df['공급단가'] / filtered_df['주문수량']
        filtered_df['단위공급단가'] = filtered_df['단위공급단가'].replace([float('inf'), -float('inf')], 0).fillna(0)
        filtered_df['이익'] = filtered_df['실결제 금액'] - (filtered_df['단위공급단가'] * filtered_df['주문-취소 수량'])
        filtered_df['이익률'] = (filtered_df['이익'] / filtered_df['실결제 금액'] * 100).replace([float('inf'), -float('inf')], 0).fillna(0)
    else:
        filtered_df['이익'] = 0
        filtered_df['이익률'] = 0

    # 주요 지표 (KPI)
    # 주요 지표 (KPI)
    st.markdown("### 📌 주요 실적 요약")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    total_sales = filtered_df['실결제 금액'].sum()
    total_profit = filtered_df['이익'].sum()
    total_qty = filtered_df['주문수량'].sum()
    cancel_qty = filtered_df['취소수량'].sum()
    
    avg_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
    cancel_rate = (cancel_qty / total_qty * 100) if total_qty > 0 else 0
    avg_order = total_sales / len(filtered_df) if len(filtered_df) > 0 else 0

    with col1:
        st.metric("전체 매출액", f"{total_sales:,.0f}원")
    with col2:
        st.metric("총 주문 건수", f"{len(filtered_df):,}건")
    with col3:
        st.metric("실 판매 수량", f"{filtered_df['주문-취소 수량'].sum():,.0f}개")
    with col4:
        st.metric("평균 객단가", f"{avg_order:,.0f}원")
    with col5:
        st.metric("평균 이익률", f"{avg_margin:.1f}%")
    with col6:
        st.metric("평균 취소율", f"{cancel_rate:.1f}%")

    st.markdown("---")

    # 탭 구성
    tab1, tab_funnel, tab_customer, tab2, tab5, tab6 = st.tabs([
        "📉 성과 추이", 
        "🌪️ 퍼널 분석",
        "👥 고객 분석",
        "👨‍🏫 셀러 분석", 
        "🍏 품종/상품 분석", 
        "📊 지역/채널 분석"
    ])

    with tab1:
        st.subheader("📉 기간별 성과 분석")
        
        # 인사이트 우선 배치
        st.markdown("### 💡 핵심 인사이트")
        
        # 요일별 분석 (인사이트 생성용)
        filtered_df['요일'] = filtered_df['주문일'].dt.day_name()
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_sales = filtered_df.groupby('요일')['실결제 금액'].sum().reindex(day_order)
        
        best_day = day_sales.idxmax()
        worst_day = day_sales.idxmin()
        day_names_kr = {
            'Monday': '월요일', 'Tuesday': '화요일', 'Wednesday': '수요일',
            'Thursday': '목요일', 'Friday': '금요일', 'Saturday': '토요일', 'Sunday': '일요일'
        }
        
        col_i1, col_i2, col_i3 = st.columns(3)
        with col_i1:
            st.info(f"🔥 **최고 매출 요일**: {day_names_kr[best_day]}\n\n매출: {day_sales[best_day]:,.0f}원")
        with col_i2:
            st.warning(f"📉 **최저 매출 요일**: {day_names_kr[worst_day]}\n\n매출: {day_sales[worst_day]:,.0f}원")
        with col_i3:
            avg_daily = filtered_df.groupby('주문일자')['실결제 금액'].sum().mean()
            st.success(f"📊 **일평균 매출**\n\n{avg_daily:,.0f}원")
        
        st.markdown("---")
        
        # 차트 병렬 배치
        col_t1_1, col_t1_2 = st.columns(2)
        
        with col_t1_1:
            st.subheader("일자별 매출 추이")
            # 일별 집계
            daily_sales = filtered_df.groupby('주문일자').agg({
                '실결제 금액': 'sum',
                '주문번호': 'count'
            }).reset_index()
            
            fig_trend = go.Figure()
            fig_trend.add_trace(go.Scatter(x=daily_sales['주문일자'], y=daily_sales['실결제 금액'], name='매출액', line=dict(color='orange', width=3)))
            fig_trend.update_layout(title="일자별 매출액 변화", xaxis_title="날짜", yaxis_title="매출액 (원)", height=400)
            st.plotly_chart(fig_trend, use_container_width=True)
            
        with col_t1_2:
            st.subheader("요일별 매출 비중")
            # 요일별 분석
            day_sales_reset = day_sales.reset_index()
            day_sales_reset.columns = ['요일', '실결제 금액']
            
            fig_day = px.bar(day_sales_reset, x='요일', y='실결제 금액', title="요일별 매출 비중", color='실결제 금액', color_continuous_scale='Oranges')
            fig_day.update_layout(height=400)
            st.plotly_chart(fig_day, use_container_width=True)
        
        st.info("""
        **💡 경영 제안: 일정 최적화**
        - **주말 vs 주중**: 매출이 저조한 요일(예: 화/수)에 '게릴라 타임세일'을 배치하여 매출 평탄화를 유도하세요.
        - **추세 관리**: 일자별 그래프에서 급격한 매출 하락이 관측되는 시점의 외부 요인(날씨, 경쟁사 행사)을 기록하고 대비하세요.
        """)

    with tab2:
        st.subheader("👨‍🏫 셀러별 상세 분석")
        
        # 인사이트 우선 배치
        st.markdown("### 💡 핵심 인사이트")
        
        seller_stats = filtered_df.groupby('셀러명').agg({
            '실결제 금액': 'sum',
            '주문번호': 'count',
            '주문-취소 수량': 'sum'
        }).rename(columns={'주문번호': '주문건수'}).sort_values('실결제 금액', ascending=False)
        
        seller_stats['평균단가'] = (seller_stats['실결제 금액'] / seller_stats['주문-취소 수량']).replace([float('inf'), -float('inf')], 0).fillna(0)
        
        top_seller = seller_stats.index[0] if len(seller_stats) > 0 else "N/A"
        top_seller_sales = seller_stats.iloc[0]['실결제 금액'] if len(seller_stats) > 0 else 0
        total_sellers = len(seller_stats)
        
        col_i1, col_i2, col_i3 = st.columns(3)
        with col_i1:
            st.success(f"🏆 **1위 셀러**: {top_seller}\n\n매출: {top_seller_sales:,.0f}원")
        with col_i2:
            st.info(f"👥 **활성 셀러 수**: {total_sellers}개")
        with col_i3:
            top3_share = (seller_stats.head(3)['실결제 금액'].sum() / seller_stats['실결제 금액'].sum() * 100) if len(seller_stats) >= 3 else 0
            st.warning(f"📊 **상위 3개 셀러 점유율**\n\n{top3_share:.1f}%")
        
        st.markdown("---")
        
        # 차트 배치
        st.subheader("셀러별 상세 실적 순위")
        
        # 상위 10개 셀러 시각화
        fig_seller_bar = px.bar(seller_stats.head(10).reset_index(), x='셀러명', y='실결제 금액', 
                                title="상위 10개 셀러 매출액", color='실결제 금액', text_auto=',.0f')
        st.plotly_chart(fig_seller_bar, use_container_width=True)
        
        st.dataframe(seller_stats.style.format({
            '실결제 금액': '{:,.0f}',
            '주문건수': '{:,.0f}',
            '주문-취소 수량': '{:,.0f}',
            '평균단가': '{:,.0f}'
        }), use_container_width=True)

        st.info("""
        **💡 경영 제안: 셀러 관리(CRM)**
        - **Super Seller (상위 10%)**: 전체 매출을 견인하는 핵심 파트너입니다. 전담 MD 배정 및 물류 우선권을 제공하여 이탈을 방지하세요.
        - **Rising Star (중위권)**: 성장 가능성이 보인다면 '단독 기획전' 제안을 통해 상위권 진입을 유도하세요.
        """)
        
        CVR 분석 보고서 통합
        st.markdown("---")
        with st.expander("📊 셀러별 주문 전환율(CVR) 분석 보고서 보기"):
            report = load_markdown_report('docs/analysis/cvr_analysis_report.md')
            if report:
                st.markdown(report)
            else:
                st.warning("CVR 분석 보고서를 찾을 수 없습니다.")

    with tab_funnel:
        st.subheader("🌪️ 구매 전환 퍼널 분석")
        
        # 데이터 준비 (방문, 클릭, 주문)
        if visit_df is not None and click_df is not None:
            # 1. 방문자 수 (Selected Date Range)
            v_mask = (visit_df['일자'] >= date_range[0]) & (visit_df['일자'] <= date_range[1])
            # DAU 전체(회원) 컬럼에서 숫자만 추출 (예: '780 (89)' -> 780)
            v_filtered = visit_df[v_mask].copy()
            v_filtered['방문자'] = v_filtered['DAU 전체(회원)'].apply(extract_numeric_value)
            total_visits = v_filtered['방문자'].sum()
            
            # 2. 클릭 수
            # salesclick_1.csv의 '합계' 컬럼 활용 (예: '16649 1551 (9.32%)' -> 16649)
            total_clicks = click_df['합계'].apply(extract_numeric_value).sum()
            
            # 3. 주문 수
            total_orders = len(filtered_df)
            
            # 퍼널 차트 데이터
            funnel_data = pd.DataFrame({
                '단계': ['단순 방문', '상품 클릭', '최종 주문'],
                '수치': [total_visits, total_clicks, total_orders]
            })
            
            col_f1, col_f2 = st.columns([2, 1])
            
            with col_f1:
                fig_funnel = px.funnel(funnel_data, x='수치', y='단계', title="전체 구매 여정 퍼널")
                st.plotly_chart(fig_funnel, use_container_width=True)
            
            with col_f2:
                st.markdown("#### 📊 단계별 전환율")
                visit_to_click = (total_clicks / total_visits * 100) if total_visits > 0 else 0
                click_to_order = (total_orders / total_clicks * 100) if total_clicks > 0 else 0
                overall_cvr = (total_orders / total_visits * 100) if total_visits > 0 else 0
                
                st.metric("방문 → 클릭 전환율", f"{visit_to_click:.1f}%")
                st.metric("클릭 → 주문 전환율", f"{click_to_order:.1f}%")
                st.metric("전체 구매 전환율", f"{overall_cvr:.1f}%")
            
            st.markdown("---")
            
            # 상품별 클릭 vs 주문 전환 분석
            st.subheader("🍏 상품별 클릭 대비 주문 효율 (CVR Top 10)")
            # 클릭 데이터와 주문 데이터 결합 (상품명 기준)
            order_by_prod = filtered_df.groupby('상품명').size().reset_index(name='주문건수')
            # 클릭 데이터 정제
            click_by_prod = click_df[['상품명', '합계']].copy()
            click_by_prod.columns = ['상품명', '클릭수']
            click_by_prod['클릭수'] = click_by_prod['클릭수'].apply(extract_numeric_value)
            
            funnel_prod = pd.merge(click_by_prod, order_by_prod, on='상품명', how='inner')
            funnel_prod['CVR(%)'] = (funnel_prod['주문건수'] / funnel_prod['클릭수'] * 100).replace([float('inf')], 0).fillna(0)
            
            top10_cvr = funnel_prod[funnel_prod['클릭수'] > 10].nlargest(10, 'CVR(%)')
            
            fig_prod_cvr = px.bar(top10_cvr, x='상품명', y='CVR(%)', color='CVR(%)', 
                                  title="상품별 주문 전환율 (클릭 10건 이상)",
                                  text_auto='.1f', color_continuous_scale='YlGnBu')
            st.plotly_chart(fig_prod_cvr, use_container_width=True)
            
            st.info("""
            **💡 퍼널 인사이트**
            - **이탈 구역 확인**: 방문 대비 클릭이 낮다면 '메인 페이지/배너' 매력도를, 클릭 대비 주문이 낮다면 '상세페이지/가격' 경쟁력을 점검하세요.
            - **고전환 상품**: CVR이 높은 상품은 트래픽(광고)만 보강하면 매출이 급증할 가능성이 매우 높습니다.
            """)
            
        else:
            st.warning("방문 데이터(`salesvisit_1.csv`) 또는 클릭 데이터(`salesclick_1.csv`)를 로드할 수 없어 퍼널 분석을 표시할 수 없습니다.")

    with tab_customer:
        st.subheader("👥 고객 상세 분석 (RFM & Retention)")
        
        if not filtered_df.empty and 'UID' in filtered_df.columns:
            # RFM 계산
            # 기준일: 마지막 주문일 + 1일
            latest_date = filtered_df['주문일'].max() + pd.Timedelta(days=1)
            
            customer_rfm = filtered_df.groupby('UID').agg({
                '주문일': lambda x: (latest_date - x.max()).days, # Recency
                '주문번호': 'count',                             # Frequency
                '실결제 금액': 'sum'                             # Monetary
            }).rename(columns={'주문일': 'Recency', '주문번호': 'Frequency', '실결제 금액': 'Monetary'})
            
            # RFM 점수 계산 (5분위수 기준)
            # 수치가 작을수록 좋은 Recency는 labels를 거꾸로
            def rfm_score(df):
                # rank(method='first')를 사용하여 모든 값에 고유한 순위를 부여함으로써 qcut 오류 방지
                df['R_Score'] = pd.qcut(df['Recency'].rank(method='first'), 5, labels=[5, 4, 3, 2, 1])
                df['F_Score'] = pd.qcut(df['Frequency'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
                df['M_Score'] = pd.qcut(df['Monetary'].rank(method='first'), 5, labels=[1, 2, 3, 4, 5])
                return df
            
            customer_rfm = rfm_score(customer_rfm)
            
            # 세그먼트 분류 (간소화)
            def segment_customer(df):
                df['Total_Score'] = df['R_Score'].astype(int) + df['F_Score'].astype(int) + df['M_Score'].astype(int)
                if df['Total_Score'] >= 13: return 'VIP 고객'
                elif df['Total_Score'] >= 10: return '충성 고객'
                elif df['R_Score'].astype(int) >= 4: return '신규 고객'
                elif df['R_Score'].astype(int) <= 2: return '이탈 위험'
                else: return '일반 고객'
            
            customer_rfm['Segment'] = customer_rfm.apply(segment_customer, axis=1)
            
            col_c1, col_c2 = st.columns(2)
            
            with col_c1:
                st.markdown("#### 고객 세그먼트 분포")
                seg_counts = customer_rfm['Segment'].value_counts().reset_index()
                seg_counts.columns = ['Segment', 'count']
                fig_seg = px.pie(seg_counts, names='Segment', values='count', hole=0.4, title="고객 등급별 비중",
                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                st.plotly_chart(fig_seg, use_container_width=True)
            
            with col_c2:
                st.markdown("#### 세그먼트별 매출 기여도")
                seg_monetary = customer_rfm.groupby('Segment')['Monetary'].sum().reset_index()
                fig_seg_m = px.bar(seg_monetary, x='Segment', y='Monetary', color='Segment', 
                                   title="등급별 총 매출액", text_auto=',.0f')
                st.plotly_chart(fig_seg_m, use_container_width=True)
            
            st.markdown("---")
            
            # 재구매 분석
            st.subheader("🔁 재구매 및 리텐션 분석")
            # 고객별 주문 간격 계산
            reorder_df = filtered_df.sort_values(['UID', '주문일'])
            reorder_df['prev_order_date'] = reorder_df.groupby('UID')['주문일'].shift(1)
            reorder_df['order_interval'] = (reorder_df['주문일'] - reorder_df['prev_order_date']).dt.days
            
            intervals = reorder_df.dropna(subset=['order_interval'])
            
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                if not intervals.empty:
                    fig_interval = px.histogram(intervals, x='order_interval', nbins=30, 
                                                title="재구매 주기 분포 (일)", labels={'order_interval': '주문 간격(일)'},
                                                color_discrete_sequence=['skyblue'])
                    st.plotly_chart(fig_interval, use_container_width=True)
                else:
                    st.info("재구매 데이터가 충분하지 않습니다.")
            
            with col_r2:
                # 재구매 비중
                total_cust = customer_rfm.index.nunique()
                repurchase_cust = customer_rfm[customer_rfm['Frequency'] > 1].index.nunique()
                st.metric("전체 고객 수", f"{total_cust:,}명")
                st.metric("재구매 고객 수", f"{repurchase_cust:,}명")
                st.metric("재구매율(%)", f"{(repurchase_cust/total_cust*100):.1f}%")
            
            st.info("""
            **💡 고객 전략 인사이트**
            - **VIP 고객 케어**: 상위 13점 이상의 VIP 고객은 전체 매출의 상당 부분을 차지합니다. 전용 쿠폰이나 시크릿 할인을 제공하세요.
            - **이탈 위험 방지**: R 점수가 낮은 고객은 최근 방문이 뜸한 상태입니다. '보고 싶었다'는 메시지와 함께 복귀 쿠폰 발송을 권장합니다.
            - **재구매 주기**: 평균 재구매 주기에 맞춰 '정기 배송' 알림톡을 발송하면 리텐션을 높일 수 있습니다.
            """)
        else:
            st.warning("고객 식별 데이터(UID)가 없어 고객 분석을 수행할 수 없습니다.")

    with tab2:
        st.subheader("👨‍🏫 셀러 실적 및 심층 분석")
        
        # 인사이트 우선 배치
        st.markdown("### 💡 핵심 인사이트")
        
        # 셀러별 핵심 지표 계산
        seller_deep = filtered_df.groupby('셀러명').agg({
            '실결제 금액': 'sum',
            '이익': 'sum',
            '주문수량': 'sum',
            '취소수량': 'sum',
            'UID': 'nunique',
            '주문번호': 'count'
        }).rename(columns={
            '실결제 금액': '매출액',
            '주문번호': '주문건수',
            'UID': '고유고객수'
        })
        
        seller_deep['이익률(%)'] = (seller_deep['이익'] / seller_deep['매출액'] * 100).replace([float('inf')], 0).fillna(0)
        seller_deep['취소율(%)'] = (seller_deep['취소수량'] / seller_deep['주문수량'] * 100).replace([float('inf')], 0).fillna(0)
        seller_deep['재구매지수'] = (seller_deep['주문건수'] / seller_deep['고유고객수']).replace([float('inf')], 0).fillna(1)
        seller_deep = seller_deep.sort_values('매출액', ascending=False)
        
        top_seller = seller_deep.index[0] if not seller_deep.empty else "N/A"
        top_seller_sales = seller_deep.iloc[0]['매출액'] if not seller_deep.empty else 0
        
        col_i1, col_i2, col_i3 = st.columns(3)
        with col_i1:
            st.success(f"🏆 **1위 셀러**: {top_seller}\n\n매출: {top_seller_sales:,.0f}원")
        with col_i2:
            st.info(f"👥 **활성 셀러 수**: {len(seller_deep)}개")
        with col_i3:
            top3_share = (seller_deep.head(3)['매출액'].sum() / seller_deep['매출액'].sum() * 100) if len(seller_deep) >= 3 else 0
            st.warning(f"📊 **상위 3개 셀러 점유율**\n\n{top3_share:.1f}%")
        
        st.markdown("---")
        
        # 차트 병렬 배치 (실적 순위 vs 효율 분석)
        col_s1, col_s2 = st.columns(2)
        
        with col_s1:
            st.subheader("셀러별 매출 순위 (Top 10)")
            fig_seller_bar = px.bar(seller_deep.head(10).reset_index(), x='셀러명', y='매출액', 
                                    color='매출액', text_auto=',.0f', color_continuous_scale='Oranges')
            fig_seller_bar.update_layout(height=400)
            st.plotly_chart(fig_seller_bar, use_container_width=True)
            
        with col_s2:
            st.subheader("매출액 vs 이익률 분석")
            fig_profit = px.scatter(
                seller_deep.head(20).reset_index(), 
                x='매출액', y='이익률(%)', size='주문건수', color='이익률(%)',
                hover_data=['셀러명'], color_continuous_scale='Viridis'
            )
            fig_profit.update_layout(height=400)
            st.plotly_chart(fig_profit, use_container_width=True)
            
        st.markdown("---")
        
        # 지역 분포 히트맵
        st.subheader("셀러별 주요 판매 지역 분포")
        top10_seller_names = seller_deep.head(10).index
        seller_region_data = filtered_df[filtered_df['셀러명'].isin(top10_seller_names)].groupby(['셀러명', '광역지역(정식)'])['주문번호'].count().reset_index()
        seller_region_data.columns = ['셀러명', '지역', '주문건수']
        
        fig_region_heat = px.density_heatmap(
            seller_region_data, x='지역', y='셀러명', z='주문건수',
            color_continuous_scale='Oranges'
        )
        st.plotly_chart(fig_region_heat, use_container_width=True)
        
        # 상세 데이터 테이블
        with st.expander("📄 셀러별 상세 지표 테이블 보기"):
            st.dataframe(seller_deep.style.format({
                '매출액': '{:,.0f}', '이익': '{:,.0f}', '이익률(%)': '{:.1f}',
                '주문건수': '{:,.0f}', '재구매지수': '{:.2f}', '취소율(%)': '{:.1f}'
            }), use_container_width=True)
            
        st.info("""
        **💡 셀러 전략 제언**
        - **효율 극대화**: 이익률이 높지만 매출이 낮은 셀러는 트래픽(광고)을 지원하여 규모를 키워야 합니다.
        - **리스크 관리**: 취소율이 평균 대비 높은 셀러는 품질 관리가 시급합니다.
        """)

        # 셀러별 유입경로 분석 통합 추가
        st.markdown("---")
        st.markdown("### 📊 셀러별 유입경로 집중도(HHI) 분석")
        
        if '주문경로' in filtered_df.columns:
            # 셀러 선택 (상위 10개 기본 선택)
            all_sellers = seller_deep.head(20).index.tolist()
            selected_sellers = st.multiselect(
                "분석할 셀러 선택 (최대 10개 권장)",
                options=all_sellers,
                default=all_sellers[:5] if len(all_sellers) >= 5 else all_sellers,
                help="셀러를 선택하여 유입경로 집중도와 성과를 분석합니다"
            )
            
            if selected_sellers:
                # HHI 계산 함수
                def calculate_channel_hhi(df, seller):
                    """셀러별 채널 집중도(HHI) 계산"""
                    seller_data = df[df['셀러명'] == seller]
                    if len(seller_data) == 0:
                        return 0
                    channel_sales = seller_data.groupby('주문경로')['실결제 금액'].sum()
                    total = channel_sales.sum()
                    if total == 0:
                        return 0
                    shares = (channel_sales / total * 100) ** 2
                    return shares.sum()
                
                # 전략 제언 생성 함수
                def generate_strategy(hhi, top_channel, sales, profit_margin):
                    """데이터 기반 전략 제언 생성"""
                    strategies = []
                    
                    if hhi > 5000:
                        strategies.append(f"⚠️ **채널 다각화 필요**: '{top_channel}' 의존도가 매우 높습니다 (HHI: {hhi:.0f}). 리스크 분산을 위해 다른 채널 확대를 권장합니다.")
                    elif hhi < 2000:
                        strategies.append(f"💡 **채널 효율화**: 채널이 과도하게 분산되어 있습니다 (HHI: {hhi:.0f}). 성과가 좋은 채널에 집중하여 효율을 높이세요.")
                    else:
                        strategies.append(f"✅ **적정 수준**: 채널 집중도가 양호합니다 (HHI: {hhi:.0f}).")
                    
                    if profit_margin < 25:
                        strategies.append(f"📉 **수익성 개선**: 이익률({profit_margin:.1f}%)이 낮습니다. '{top_channel}' 채널의 마케팅 비용을 재검토하세요.")
                    elif profit_margin > 35:
                        strategies.append(f"🌟 **고수익 유지**: 이익률({profit_margin:.1f}%)이 우수합니다. '{top_channel}' 채널 투자를 확대하세요.")
                    
                    return "\n".join(strategies)
                
                # 분석 데이터 수집
                analysis_data = []
                for seller in selected_sellers:
                    seller_df = filtered_df[filtered_df['셀러명'] == seller]
                    
                    # 주요 지표 계산
                    hhi = calculate_channel_hhi(filtered_df, seller)
                    total_sales = seller_df['실결제 금액'].sum()
                    total_profit = seller_df['이익'].sum()
                    profit_margin = (total_profit / total_sales * 100) if total_sales > 0 else 0
                    
                    # 주력 채널
                    channel_sales = seller_df.groupby('주문경로')['실결제 금액'].sum()
                    top_channel = channel_sales.idxmax() if len(channel_sales) > 0 else "N/A"
                    top_channel_share = (channel_sales.max() / total_sales * 100) if total_sales > 0 else 0
                    
                    analysis_data.append({
                        '셀러명': seller,
                        'HHI': hhi,
                        '주력채널': top_channel,
                        '주력채널비중': top_channel_share,
                        '매출액': total_sales,
                        '이익률': profit_margin
                    })
                
                # 시각화: HHI vs 성과
                if analysis_data:
                    analysis_df = pd.DataFrame(analysis_data)
                    
                    col_ch1, col_ch2 = st.columns(2)
                    
                    with col_ch1:
                        # HHI vs 매출액
                        fig_hhi_sales = px.scatter(
                            analysis_df,
                            x='HHI',
                            y='매출액',
                            size='이익률',
                            color='이익률',
                            hover_data=['셀러명', '주력채널'],
                            title="유입경로 집중도(HHI) vs 매출액",
                            labels={'HHI': '채널 집중도 (HHI)', '매출액': '매출액 (원)'},
                            color_continuous_scale='Viridis'
                        )
                        fig_hhi_sales.add_hline(y=analysis_df['매출액'].median(), line_dash="dash", 
                                               annotation_text="중앙값", line_color="red")
                        st.plotly_chart(fig_hhi_sales, use_container_width=True)
                    
                    with col_ch2:
                        # HHI vs 이익률
                        fig_hhi_profit = px.scatter(
                            analysis_df,
                            x='HHI',
                            y='이익률',
                            size='매출액',
                            color='셀러명',
                            hover_data=['주력채널', '주력채널비중'],
                            title="유입경로 집중도(HHI) vs 이익률",
                            labels={'HHI': '채널 집중도 (HHI)', '이익률': '이익률 (%)'}
                        )
                        fig_hhi_profit.add_hline(y=30, line_dash="dash", 
                                                annotation_text="목표 이익률 30%", line_color="green")
                        st.plotly_chart(fig_hhi_profit, use_container_width=True)
                    
                    # 셀러별 상세 분석 (클릭하면 보이는 형태)
                    st.markdown("---")
                    st.markdown("#### 셀러별 상세 전략 제언")
                    
                    for idx, row in analysis_df.iterrows():
                        seller = row['셀러명']
                        seller_df = filtered_df[filtered_df['셀러명'] == seller]
                        
                        with st.expander(f"📊 {seller} - 유입경로 분석 및 전략"):
                            col_s1, col_s2, col_s3 = st.columns(3)
                            
                            with col_s1:
                                st.metric("채널 집중도 (HHI)", f"{row['HHI']:.0f}")
                                st.caption("5000 이상: 고집중 / 2000 이하: 분산")
                            
                            with col_s2:
                                st.metric("주력 채널", row['주력채널'])
                                st.caption(f"비중: {row['주력채널비중']:.1f}%")
                            
                            with col_s3:
                                st.metric("이익률", f"{row['이익률']:.1f}%")
                                st.caption(f"매출: {row['매출액']:,.0f}원")
                            
                            # 채널별 매출 분포
                            channel_dist = seller_df.groupby('주문경로')['실결제 금액'].sum().reset_index()
                            channel_dist.columns = ['채널', '매출액']
                            channel_dist = channel_dist.sort_values('매출액', ascending=False)
                            
                            fig_channel = px.bar(
                                channel_dist,
                                x='채널',
                                y='매출액',
                                title=f"{seller} - 채널별 매출 분포",
                                color='매출액',
                                color_continuous_scale='Blues'
                            )
                            st.plotly_chart(fig_channel, use_container_width=True)
                            
                            # 전략 제언
                            st.markdown("##### 💡 맞춤 전략 제언")
                            strategy = generate_strategy(
                                row['HHI'], 
                                row['주력채널'], 
                                row['매출액'], 
                                row['이익률']
                            )
                            st.info(strategy)
                
            else:
                st.warning("분석할 셀러를 선택해주세요.")
        else:
            st.warning("데이터에 '주문경로' 컬럼이 없어 유입경로 분석을 수행할 수 없습니다.")

    with tab5:
        st.subheader("🍏 품종 및 상품 상세 분석")
        
        # 인사이트 우선 배치
        st.markdown("### 💡 핵심 인사이트")
        variety_stats = filtered_df.groupby('품종').agg({
            '실결제 금액': 'sum', '이익': 'sum', '주문번호': 'count'
        })
        variety_stats['이익률'] = (variety_stats['이익'] / variety_stats['실결제 금액'] * 100).fillna(0)
        variety_stats = variety_stats.sort_values('실결제 금액', ascending=False)
        
        top_v = variety_stats.index[0] if not variety_stats.empty else "N/A"
        top_v_sales = variety_stats.iloc[0]['실결제 금액'] if not variety_stats.empty else 0
        best_m_v = variety_stats['이익률'].idxmax() if not variety_stats.empty else "N/A"
        
        col_t5_i1, col_t5_i2, col_t5_i3 = st.columns(3)
        with col_t5_i1:
            st.success(f"🥇 **매출 1위 품종**: {top_v}\n\n매출: {top_v_sales:,.0f}원")
        with col_t5_i2:
            st.info(f"💰 **최고 이익률 품종**: {best_m_v}\n\n이익률: {variety_stats.get('이익률', pd.Series([0])).max():.1f}%")
        with col_t5_i3:
            st.warning(f"📊 **판매 품종 수**: {len(variety_stats)}개")
            
        st.markdown("---")
        
        # 차트 병렬 배치: 매출 비중 vs 이익률
        col_t5_1, col_t5_2 = st.columns(2)
        with col_t5_1:
            st.subheader("품종별 매출 비중")
            fig_pie = px.pie(variety_stats.reset_index(), values='실결제 금액', names='품종', hole=0.4, title="품종별 매출 분포")
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_t5_2:
            st.subheader("품종별 이익률 비교 (Top 10)")
            top10_margin = variety_stats[variety_stats['실결제 금액'] > 300000].nlargest(10, '이익률')
            fig_margin = px.bar(top10_margin.reset_index(), x='품종', y='이익률', color='이익률', 
                                title="품종별 평균 이익률 (%)", text_auto='.1f', color_continuous_scale='Greens')
            st.plotly_chart(fig_margin, use_container_width=True)
            
        st.markdown("---")
        
        # 세그먼트 및 이벤트 분석 (구 Tab 4 내용 통합)
        st.subheader("📊 상품 세그먼트 및 이벤트 분석")
        col_seg1, col_seg2 = st.columns(2)
        
        with col_seg1:
            st.markdown("#### 이벤트 및 선물세트 성과")
            if '이벤트 여부' in filtered_df.columns:
                event_s = filtered_df.groupby('이벤트 여부')['이익률'].mean().reset_index()
                fig_ev = px.bar(event_s, x='이벤트 여부', y='이익률', color='이벤트 여부', title="이벤트 여부별 평균 이익률 (%)", color_discrete_sequence=['#A8D5BA', '#FFB347'])
                st.plotly_chart(fig_ev, use_container_width=True)
            
        with col_seg2:
            st.markdown("#### 선물세트 vs 가정용 가격대 분포")
            if '선물세트_여부' in filtered_df.columns:
                gift_p = filtered_df.groupby(['선물세트_여부', '가격대'])['주문번호'].count().reset_index()
                fig_gift = px.bar(gift_p, x='가격대', y='주문번호', color='선물세트_여부', barmode='group', title="선물세트 vs 가정용 분포")
                st.plotly_chart(fig_gift, use_container_width=True)
                
        # 품종 X 등급 히트맵
        if '상품성등급_그룹' in filtered_df.columns:
            st.markdown("#### 품종 × 상품 등급 매출 히트맵")
            cross_p = filtered_df.groupby(['품종', '상품성등급_그룹'])['실결제 금액'].sum().reset_index().pivot(index='품종', columns='상품성등급_그룹', values='실결제 금액').fillna(0)
            fig_heat = px.imshow(cross_p, color_continuous_scale='YlOrRd', aspect="auto", title="품종별 등급 매출 분포")
            st.plotly_chart(fig_heat, use_container_width=True)
            
        st.info("""
        **💡 상품 및 세그먼트 전략**
        - **Premium Focus**: '프리미엄' 등급은 마진율이 높으므로 브랜딩을 강화하세요.
        - **Event Synergy**: 이벤트 상품(y)은 낮은 마진을 높은 구매량으로 상쇄하고 있는지 확인이 필요합니다.
        """)
        
        st.markdown("---")
        with st.expander("📊 상품/품종 심화 분석 리포트 (EDA)"):
            report = load_markdown_report('docs/analysis/eda_comprehensive_report.md')
            if report: st.markdown(report)
            else:
                st.warning("EDA 종합 분석 보고서를 찾을 수 없습니다.")

    with tab6:
        st.subheader("🌍 지역 및 유입 채널 분석")
        
        # 인사이트 우선 배치
        st.markdown("### 💡 핵심 인사이트")
        
        r_sales = filtered_df.groupby('광역지역(정식)')['실결제 금액'].sum().sort_values(ascending=False)
        top_r = r_sales.index[0] if not r_sales.empty else "N/A"
        c_sales = filtered_df.groupby('주문경로')['실결제 금액'].sum().sort_values(ascending=False)
        top_c = c_sales.index[0] if not c_sales.empty else "N/A"
        
        col_t6_i1, col_t6_i2, col_t6_i3 = st.columns(3)
        with col_t6_i1:
            st.success(f"🌍 **최대 매출 지역**: {top_r}\n\n매출: {r_sales.max():,.0f}원")
        with col_t6_i2:
            st.info(f"📱 **주력 채널**: {top_c}")
        with col_t6_i3:
            st.warning(f"📍 **판매 지역 수**: {filtered_df['광역지역(정식)'].nunique()}개")
            
        st.markdown("---")
        
        # 차트 병렬 배치: 지역별 매출 vs 채널별 매출
        col_t6_1, col_t6_2 = st.columns(2)
        with col_t6_1:
            st.subheader("지역별 매출 순위 (Top 10)")
            fig_r = px.bar(r_sales.head(10).reset_index(), x='광역지역(정식)', y='실결제 금액', 
                           color='실결제 금액', color_continuous_scale='Reds', text_auto=',.0f')
            st.plotly_chart(fig_r, use_container_width=True)
            
        with col_t6_2:
            st.subheader("유입 채널별 비중")
            fig_c = px.pie(c_sales.reset_index(), values='실결제 금액', names='주문경로', hole=0.4)
            st.plotly_chart(fig_c, use_container_width=True)
            
        st.markdown("---")
        
        # 지역별 경쟁 분석 (HHI) & 탑 3 전략
        st.subheader("📍 지역 기반 경쟁력 및 타겟팅 전략")
        col_r1, col_r2 = st.columns([1, 1])
        
        with col_r1:
            st.markdown("#### 지역별 셀러 집중도 (HHI)")
            reg_s = filtered_df.groupby(['광역지역(정식)', '셀러명'])['실결제 금액'].sum().reset_index()
            hhi_data = []
            for r in r_sales.head(10).index:
                r_d = reg_s[reg_s['광역지역(정식)'] == r]
                total = r_d['실결제 금액'].sum()
                hhi = ((r_d['실결제 금액'] / total * 100)**2).sum()
                hhi_data.append({'지역': r, 'HHI': hhi})
            hhi_df = pd.DataFrame(hhi_data)
            fig_hhi = px.bar(hhi_df, x='지역', y='HHI', color='HHI', color_continuous_scale='Plasma')
            st.plotly_chart(fig_hhi, use_container_width=True)
            
        with col_r2:
            st.markdown("#### 핵심 3개 지역 맞춤 전략")
            top3 = r_sales.head(3).index.tolist()
            for i, r in enumerate(top3):
                with st.expander(f"📍 {i+1}위: {r} 전략"):
                    r_d = filtered_df[filtered_df['광역지역(정식)'] == r]
                    top_v = r_d.groupby('품종')['실결제 금액'].sum().idxmax()
                    st.write(f"**선호 품종**: {top_v}")
                    if r == '서울': st.info("💡 제안: 프리미엄 선물세트 및 새벽 배송 강화")
                    elif r == '경기': st.info("💡 제안: 가정용 대용량 패키지 중심 판촉")
                    else: st.info("💡 제안: 지역 특화 프로모션 및 재구매 유도")
                    
        st.markdown("---")
        
        # 기존 요일/시간 분석 (Golden Time) 통합
        st.subheader("⏰ 구매 시간대 및 요일 분석 (Golden Time)")
        if '주문일' in filtered_df.columns:
            df_dt = filtered_df.copy()
            df_dt['Hour'] = df_dt['주문일'].dt.hour
            df_dt['Day'] = df_dt['주문일'].dt.day_name()
            
            time_dist = df_dt.groupby(['Day', 'Hour'])['실결제 금액'].sum().reset_index()
            fig_time = px.line(time_dist, x='Hour', y='실결제 금액', color='Day', title="요일/시간별 매출 추이")
            st.plotly_chart(fig_time, use_container_width=True)
            
        st.info("""
        **💡 마케팅 전략 제언**
        - **Golden Time**: 매출 피크 시간대에 맞춰 타겟 광고를 집행하여 ROAS를 극대화하세요.
        - **Channel Mix**: SNS 유입 비중이 높다면, 결제 페이지 간소화(CVR 개선)가 필수입니다.
        """)
        
        st.markdown("---")
        with st.expander("📊 마케팅 및 경영 전략 리포트 보기"):
            report = load_markdown_report('docs/analysis/marketing_strategy_report.md')
            if report: st.markdown(report)
            else: st.warning("보고서 파일 없음")

else:
    st.error("데이터 파일을 찾을 수 없습니다. 경로: 'data/preprocessed_data.csv'")
