import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="제주 세일즈 분석 대시보드", layout="wide")

# 데이터 로드 환경 설정
import glob
import re

# 데이터 로드 환경 설정
def get_latest_data_path():
    # 1. 버전 패턴을 가진 파일들 리스팅
    files = glob.glob('data/preprocessed_data_*.csv')
    
    # 기본 파일도 후보에 포함
    if os.path.exists('data/preprocessed_data.csv'):
        files.append('data/preprocessed_data.csv')
    
    if not files:
        return None
        
    # 파일 수정 시간(mtime) 기준으로 정렬하여 가장 최신 파일 반환
    # 사용자가 preprocessed_data_1.csv가 최신이라고 명시함에 따라 실제 mtime을 따릅니다.
    latest_file = max(files, key=os.path.getmtime)
    return latest_file

DATA_PATH = get_latest_data_path()

@st.cache_data
def load_data(path):
    if path and os.path.exists(path):
        try:
            # 로딩 시 숫자 컬럼을 명시적으로 처리
            df = pd.read_csv(path, encoding='utf-8-sig')
        except:
            df = pd.read_csv(path, encoding='cp949')
        
        # 금액 데이터 처리 보강
        def clean_money(val):
            if pd.isna(val):
                return 0.0
            if isinstance(val, str):
                # 콤마, 공백 제거 후 숫자로 변환
                clean_val = val.replace(',', '').replace(' ', '').strip()
                try:
                    return float(clean_val)
                except:
                    return 0.0
            return float(val) if val is not None else 0.0
        
        # 대상 컬럼 리스트
        money_cols = ['실결제 금액', '결제금액', '공급단가', '판매단가', '주문취소 금액', '결제금액(통합)']
        # 모든 금액 컬럼 정제
        for col in money_cols:
            if col in df.columns:
                df[col] = df[col].apply(clean_money)

        # 실결제 금액 보정 (버전별 컬럼 유실 대비)
        if '실결제 금액' in df.columns and '결제금액(통합)' in df.columns:
            # 실결제 금액이 0 이하이거나 NaN인 경우 결제금액(통합)으로 대체
            # 단, 결제금액(통합)이 0보다 큰 경우에만 대체
            mask_fix = ((df['실결제 금액'] <= 0) | (df['실결제 금액'].isna())) & (df['결제금액(통합)'] > 0)
            df.loc[mask_fix, '실결제 금액'] = df.loc[mask_fix, '결제금액(통합)']
            
            # 결제금액도 동일하게 처리
            if '결제금액' in df.columns:
                df.loc[mask_fix, '결제금액'] = df.loc[mask_fix, '결제금액(통합)']
        
        # 수량 데이터 처리
        qty_cols = ['주문수량', '취소수량', '주문-취소 수량']
        for col in qty_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        # 날짜 처리
        if '주문일' in df.columns:
            df['주문일'] = pd.to_datetime(df['주문일'], errors='coerce')
            # 파싱 실패(NaT) 제거
            df = df.dropna(subset=['주문일'])
            df['주문일자'] = df['주문일'].dt.date
        
        # 문자열 컬럼 결측치 및 타입 처리
        if '셀러명' in df.columns:
            df['셀러명'] = df['셀러명'].fillna('미지정').astype(str)
        if '품종' in df.columns:
            df['품종'] = df['품종'].fillna('기타').astype(str)
        
        return df
    return None

df = load_data(DATA_PATH)

# 캐시/데이터 확인용 메시지 (개발용)
if df is not None:
    if '이벤트 여부' in df.columns:
        st.toast(f"데이터 로드 성공: {os.path.basename(DATA_PATH)} (이벤트 컬럼 포함)")
    else:
        st.toast(f"데이터 로드 성공: {os.path.basename(DATA_PATH)} (이벤트 컬럼 없음!)", icon="⚠️")

if df is not None:
    st.title("🍊 제주 세일즈 데이터 분석 대시보드")
    
    # 사이드바 제목
    st.sidebar.title("🛠️ 분석 설정")
    
    if df is not None:
        # 데이터 로드 상태 디버깅 (사이드바 하단)
        st.sidebar.markdown("---")
        st.sidebar.caption(f"📊 로드된 데이터: {len(df):,}행")
        total_raw_sales = df['실결제 금액'].sum()
        st.sidebar.caption(f"💰 전체 매출액(필터전): {total_raw_sales:,.0f}원")

        # 기간 필터
        min_date = df['주문일자'].min()
        max_date = df['주문일자'].max()
        
        st.sidebar.subheader("📅 분석 기간")
        date_range = st.sidebar.date_input(
            "기간 선택 (기본: 전체)",
            [min_date, max_date],
            min_value=min_date,
            max_value=max_date
        )
        
        # 날짜 필터링 (date_range가 시작/종료일 모두 있을 때만)
        if len(date_range) == 2:
            mask = (df['주문일자'] >= date_range[0]) & (df['주문일자'] <= date_range[1])
            filtered_df = df.loc[mask]
        else:
            filtered_df = df
            
        if filtered_df.empty:
            st.warning("⚠️ 선택한 필터 조건에 해당하는 데이터가 없습니다. 필터를 조정해 주세요.")
            st.stop() # 데이터가 없으면 이후 계산을 중단
    else:
        st.error("데이터를 로드하지 못했습니다.")
        st.stop()

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
    
    filtered_df = df[mask]
    
    # 이익 및 이익률 계산 (전역 적용)
    # 공급단가를 주문수량으로 나눈 단가 사용
    filtered_df['단위공급단가'] = filtered_df['공급단가'] / filtered_df['주문수량']
    filtered_df['단위공급단가'] = filtered_df['단위공급단가'].replace([float('inf'), -float('inf')], 0).fillna(0)
    filtered_df['이익'] = filtered_df['실결제 금액'] - (filtered_df['단위공급단가'] * filtered_df['주문-취소 수량'])
    filtered_df['이익률'] = (filtered_df['이익'] / filtered_df['실결제 금액'] * 100).replace([float('inf'), -float('inf')], 0).fillna(0)

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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📉 기간별 성과", 
        "👨‍🏫 셀러별 상세 분석", 
        "🔍 셀러 심층 분석",
        "🎯 추가 분석 (지역/이벤트/선물)",
        "🍏 품종/상품 분석", 
        "📊 지역/채널 분석",
        "📈 마케팅 전략 (Retention)",
        "📋 종합 전략 보고서"
    ])

    with tab1:
        st.subheader("일자별 매출 추이")
        # 일별 집계
        daily_sales = filtered_df.groupby('주문일자').agg({
            '실결제 금액': 'sum',
            '주문번호': 'count'
        }).reset_index()
        
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(x=daily_sales['주문일자'], y=daily_sales['실결제 금액'], name='매출액', line=dict(color='orange', width=3)))
        fig_trend.update_layout(title="일자별 매출액 변화", xaxis_title="날짜", yaxis_title="매출액 (원)")
        st.plotly_chart(fig_trend, use_container_width=True)
        
        # 요일별 분석
        filtered_df['요일'] = filtered_df['주문일'].dt.day_name()
        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        day_sales = filtered_df.groupby('요일')['실결제 금액'].sum().reindex(day_order).reset_index()
        
        fig_day = px.bar(day_sales, x='요일', y='실결제 금액', title="요일별 매출 비중", color='실결제 금액', color_continuous_scale='Oranges')
        st.plotly_chart(fig_day, use_container_width=True)
        
        st.info("""
        **💡 경영 제안: 일정 최적화**
        - **주말 vs 주중**: 매출이 저조한 요일(예: 화/수)에 '게릴라 타임세일'을 배치하여 매출 평탄화를 유도하세요.
        - **추세 관리**: 일자별 그래프에서 급격한 매출 하락이 관측되는 시점의 외부 요인(날씨, 경쟁사 행사)을 기록하고 대비하세요.
        """)

    with tab2:
        st.subheader("셀러별 상세 실적 순위")
        seller_stats = filtered_df.groupby('셀러명').agg({
            '실결제 금액': 'sum',
            '주문번호': 'count',
            '주문-취소 수량': 'sum'
        }).rename(columns={'주문번호': '주문건수'}).sort_values('실결제 금액', ascending=False)
        
        seller_stats['평균단가'] = (seller_stats['실결제 금액'] / seller_stats['주문-취소 수량']).replace([float('inf'), -float('inf')], 0).fillna(0)
        
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

    with tab3:
        st.subheader("🔍 셀러 심층 분석")
        
        # 이익 계산 (공급단가를 주문수량으로 나눈 단가 사용)
        filtered_df['단위공급단가'] = filtered_df['공급단가'] / filtered_df['주문수량']
        filtered_df['단위공급단가'] = filtered_df['단위공급단가'].replace([float('inf'), -float('inf')], 0).fillna(0)
        filtered_df['이익'] = filtered_df['실결제 금액'] - (filtered_df['단위공급단가'] * filtered_df['주문-취소 수량'])
        
        # 셀러별 핵심 지표
        # 셀러별 핵심 지표
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
        
        seller_deep['이익률(%)'] = (seller_deep['이익'] / seller_deep['매출액'] * 100).round(2)
        seller_deep['취소율(%)'] = (seller_deep['취소수량'] / seller_deep['주문수량'] * 100).round(2)
        seller_deep['재구매율'] = (seller_deep['주문건수'] / seller_deep['고유고객수']).round(2)
        
        seller_deep = seller_deep.sort_values('매출액', ascending=False)
        
        # 상위 15개 셀러
        top15_sellers = seller_deep.head(15)
        
        col_t3_1, col_t3_2 = st.columns(2)
        
        with col_t3_1:
            st.markdown("#### 매출 vs 이익률")
            fig_profit = px.scatter(
                top15_sellers.reset_index(), 
                x='매출액', 
                y='이익률(%)', 
                size='주문건수',
                color='이익률(%)',
                hover_data=['셀러명'],
                title="상위 15개 셀러: 매출액 vs 이익률"
            )
            st.plotly_chart(fig_profit, use_container_width=True)
        
        with col_t3_2:
            st.markdown("#### 재구매율 vs 취소율")
            fig_behavior = px.scatter(
                top15_sellers.reset_index(), 
                x='재구매율', 
                y='취소율(%)', 
                size='매출액',
                color='셀러명',
                hover_data=['매출액', '이익률(%)'],
                title="상위 15개 셀러: 재구매율 vs 취소율"
            )
            st.plotly_chart(fig_behavior, use_container_width=True)
        
        st.markdown("---")
        
        # 셀러별 지역 분포 (상위 10개 셀러)
        st.markdown("#### 셀러별 주요 판매 지역 분포")
        top10_sellers = seller_deep.head(10).index
        
        seller_region_data = filtered_df[filtered_df['셀러명'].isin(top10_sellers)].groupby(['셀러명', '광역지역(정식)'])['주문번호'].count().reset_index()
        seller_region_data.columns = ['셀러명', '지역', '주문건수']
        
        fig_region_heat = px.density_heatmap(
            seller_region_data, 
            x='지역', 
            y='셀러명', 
            z='주문건수',
            title="상위 10개 셀러의 지역별 주문 분포",
            color_continuous_scale='Oranges'
        )
        st.plotly_chart(fig_region_heat, use_container_width=True)
        
        st.markdown("---")
        
        # 상세 데이터 테이블
        st.markdown("#### 셀러별 상세 지표")
        st.dataframe(
            seller_deep[['매출액', '이익', '이익률(%)', '주문건수', '재구매율', '취소율(%)']].style.format({
                '매출액': '{:,.0f}',
                '이익': '{:,.0f}',
                '이익률(%)': '{:.2f}',
                '주문건수': '{:,.0f}',
                '재구매율': '{:.2f}',
                '취소율(%)': '{:.2f}'
            }),
            use_container_width=True
        )

        st.info("""
        **💡 경영 제안: 수익성 & 리스크 관리**
        - **고매출-저이익 셀러**: 박리다매형입니다. 판매량은 많으나 실속이 없으므로 물류비/수수료 구조 효율화를 제안하세요.
        - **고이익-저매출 셀러**: 잠재력은 있으나 노출이 부족합니다. 메인 배너 노출 등 트래픽 지원 시 ROAS가 높을 것입니다.
        - **고취소율 리스크**: 취소율이 5% 이상인 셀러는 CS/품질 모니터링 경고를 발송하고 소명 절차를 진행하세요.
        """)

    with tab4:
        st.subheader("🎯 추가 분석: 지역/이벤트/선물")
        
        # 지역별 셀러 집중도 분석
        st.markdown("### 1. 지역별 셀러 집중도 (HHI)")
        
        regional_seller = filtered_df.groupby(['광역지역(정식)', '셀러명'])['실결제 금액'].sum().reset_index()
        
        hhi_data = []
        for region in regional_seller['광역지역(정식)'].unique():
            region_data = regional_seller[regional_seller['광역지역(정식)'] == region]
            total_sales = region_data['실결제 금액'].sum()
            region_data['점유율'] = (region_data['실결제 금액'] / total_sales * 100)
            hhi = (region_data['점유율'] ** 2).sum()
            top_seller = region_data.nlargest(1, '실결제 금액').iloc[0]
            
            
            hhi_data.append({
                '지역': region,
                'HHI': hhi,
                '1위셀러': top_seller['셀러명'],
                '1위점유율': top_seller['점유율']
            })
        
        if hhi_data:
            hhi_df = pd.DataFrame(hhi_data).sort_values('HHI', ascending=False).head(10)
            
            fig_hhi = px.bar(hhi_df, x='지역', y='HHI', color='HHI', 
                             title="지역별 셀러 집중도 (HHI 지수)", 
                             hover_data=['1위셀러', '1위점유율'])
            st.plotly_chart(fig_hhi, use_container_width=True)
        else:
            st.info("선택된 조건에 대한 지역별 셀러 데이터가 불충분하여 HHI를 계산할 수 없습니다.")
        
        st.markdown("---")
        
        # 이벤트 상품 분석
        col_t4_1, col_t4_2 = st.columns(2)
        
        with col_t4_1:
            st.markdown("### 2. 이벤트 상품 구매량 비교")
            if '이벤트 여부' in filtered_df.columns:
                event_stats = filtered_df.groupby('이벤트 여부').agg({
                    '주문-취소 수량': 'mean',
                    '주문번호': 'count'
                }).reset_index()
                event_stats.columns = ['이벤트여부', '평균구매량', '주문건수']
                
                fig_event_vol = px.bar(event_stats, x='이벤트여부', y='평균구매량', 
                                       color='이벤트여부', title="이벤트 여부별 평균 구매량")
                st.plotly_chart(fig_event_vol, use_container_width=True)
            else:
                st.info("데이터에 '이벤트 여부' 정보가 없습니다.")
        
        with col_t4_2:
            st.markdown("### 3. 이벤트 상품 이익률 비교")
            if '이벤트 여부' in filtered_df.columns:
                event_profit = filtered_df.groupby('이벤트 여부')['이익률'].mean().reset_index()
                event_profit.columns = ['이벤트여부', '평균이익률']
                
                fig_event_profit = px.bar(event_profit, x='이벤트여부', y='평균이익률', 
                                          color='이벤트여부', title="이벤트 여부별 평균 이익률 (%)")
                st.plotly_chart(fig_event_profit, use_container_width=True)
            else:
                st.info("데이터에 '이벤트 여부' 정보가 없습니다.")
        
        st.markdown("---")
        
        # 선물용 프리미엄 분석
        st.markdown("### 4. 선물세트 vs 가정용 가격대 비교")
        
        gift_price = filtered_df.groupby(['선물세트_여부', '가격대'])['주문번호'].count().reset_index()
        gift_price.columns = ['선물세트여부', '가격대', '주문건수']
        
        fig_gift = px.bar(gift_price, x='가격대', y='주문건수', color='선물세트여부', 
                          barmode='group', title="선물세트 vs 가정용 가격대 분포")
        st.plotly_chart(fig_gift, use_container_width=True)
        
        # 평균 단가 비교
        avg_price_comp = filtered_df.groupby('선물세트_여부').agg({
            '실결제 금액': 'sum',
            '주문-취소 수량': 'sum'
        })
        avg_price_comp['평균단가'] = (avg_price_comp['실결제 금액'] / avg_price_comp['주문-취소 수량']).round(0)
        
        st.markdown("#### 평균 단가 비교")
        st.dataframe(avg_price_comp[['평균단가']].style.format({'평균단가': '{:,.0f}원'}), use_container_width=True)

        st.info("""
        **💡 경영 제안: 타겟팅 & 시즌 전략**
        - **지역 공략**: HHI가 높은(주문이 집중된) 지역은 '익일 배송' 테스트베드로 활용하여 물류 효율을 극대화하세요.
        - **이벤트 효율**: 이벤트 상품의 이익률이 너무 낮다면(역마진 우려), 미끼 상품(Loss Leader)으로 활용하되 연관 구매(Cross-selling) 유도가 잘 되고 있는지 점검해야 합니다.
        """)

    with tab5:
        col_t5_1, col_t5_2 = st.columns(2)
        with col_t5_1:
            st.subheader("품종별 매출 비중")
            variety_sales = filtered_df.groupby('품종')['실결제 금액'].sum().reset_index()
            fig_pie = px.pie(variety_sales, values='실결제 금액', names='품종', hole=0.4, title="품종별 매출 분포")
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with col_t5_2:
            st.subheader("선물세트 상세 분석")
            if '선물세트_여부' in filtered_df.columns:
                gift_df = filtered_df[filtered_df['선물세트_여부'] == '선물세트']
                if not gift_df.empty:
                    gift_pivot = gift_df.groupby(['품종', '과수 크기']).agg({'실결제 금액': 'sum'}).reset_index()
                    fig_sun = px.sunburst(gift_pivot, path=['품종', '과수 크기'], values='실결제 금액', title="선물세트 품종/크기별 분포")
                    st.plotly_chart(fig_sun, use_container_width=True)
                else:
                    st.info("선택된 기간/조건에 선물세트 데이터가 없습니다.")
        
        st.markdown("---")
        
        # [NEW] Profit Margin by Variety (V7 Analysis)
        st.subheader("💰 품종별 수익성 분석 (New)")
        if '품종' in filtered_df.columns:
            # Filter low sales varieties
            v_sum = filtered_df.groupby('품종')['실결제 금액'].sum()
            valid_v = v_sum[v_sum > 1000000].index # 100만원 이상
            
            v_stats = filtered_df[filtered_df['품종'].isin(valid_v)].groupby('품종').agg({
                '이익': 'sum',
                '실결제 금액': 'sum'
            })
            v_stats['이익률'] = (v_stats['이익'] / v_stats['실결제 금액'] * 100).fillna(0)
            v_stats = v_stats.sort_values('이익률', ascending=False).reset_index()
            
            fig_v_margin = px.bar(v_stats, x='품종', y='이익률', color='이익률',
                                  title="품종별 평균 판매 이익률 (%)", text_auto='.1f',
                                  color_continuous_scale='Greens')
            st.plotly_chart(fig_v_margin, use_container_width=True)
            st.caption("Insight: 이익률이 낮은 품종은 프로모션 비용을 축소하거나 판가를 조정해야 합니다.")

        st.info("""
        **💡 경영 제안: 상품 포트폴리오**
        - **품종 다각화**: 이익률 상위 품종의 재고를 우선 확보하고, 마케팅 예산을 집중하세요.
        - **선물세트 강화**: 선물세트는 객단가가 일반 상품 대비 높으므로(V7 데이터 확인), 명절 전용관을 운영하세요.
        """)

    with tab6:
        st.subheader("📊 6. 경영 심화 분석 (H1 ~ H3)")
        st.info("경영자 관점 심화 분석 리포트(V1~V6)에서 도출된 핵심 가설(채널, 시간, 그룹핑)을 검증하는 대시보드입니다.")
        
        col_m1, col_m2 = st.columns([1, 1])
        
        # 1. Seller x Channel (H1)
        with col_m1:
            st.markdown("### 1. 셀러별 집중 채널 (가설 1)")
            if '셀러명' in filtered_df.columns and '주문경로' in filtered_df.columns:
                # Top 10 Sellers by Revenue
                top_seller_rev = filtered_df.groupby('셀러명')['실결제 금액'].sum().nlargest(10).index
                df_top_seller = filtered_df[filtered_df['셀러명'].isin(top_seller_rev)]
                
                heatmap_data = pd.crosstab(df_top_seller['셀러명'], df_top_seller['주문경로'], 
                                         values=df_top_seller['실결제 금액'], aggfunc='sum').fillna(0)
                
                fig_heat = px.imshow(heatmap_data, text_auto=True, aspect="auto",
                                     title="상위 10개 셀러의 채널별 매출 히트맵",
                                     color_continuous_scale="Reds")
                st.plotly_chart(fig_heat, use_container_width=True)
                st.caption("Insight: 셀러마다 주력 채널이 다르며, '카카오톡'과 '인스타그램' 의존도가 높습니다.")

        # 2. Time & Day Analysis (H2)
        with col_m2:
            st.markdown("### 2. 요일별 골든 타임 (가설 2)")
            if '주문일' in filtered_df.columns:
                filtered_df['DT'] = pd.to_datetime(filtered_df['주문일'], errors='coerce')
                valid_dt = filtered_df.dropna(subset=['DT']).copy()
                valid_dt['Hour'] = valid_dt['DT'].dt.hour
                valid_dt['Day'] = valid_dt['DT'].dt.day_name()
                
                # Top 4 Days
                top_days = valid_dt.groupby('Day')['실결제 금액'].sum().nlargest(4).index
                df_days = valid_dt[valid_dt['Day'].isin(top_days)]
                
                day_hour = df_days.groupby(['Day', 'Hour'])['실결제 금액'].sum().reset_index()
                
                fig_line = px.line(day_hour, x='Hour', y='실결제 금액', color='Day',
                                   title="상위 4개 요일의 시간대별 매출 추이",
                                   markers=True)
                st.plotly_chart(fig_line, use_container_width=True)
                st.caption("Insight: 일요일 오후, 월요일 점심 등 요일별 피크 타임이 뚜렷합니다.")

        st.markdown("---")
        
        # 3. Grouping Analysis (H3 + Grouping)
        st.markdown("### 3. 그룹핑 및 취소 분석 (가설 3)")
        col_g1, col_g2, col_g3 = st.columns(3)
        
        with col_g1:
            st.markdown("#### 구매 목적 (Gift vs Personal)")
            if '목적' in filtered_df.columns:
                fig_purp = px.pie(filtered_df, names='목적', values='실결제 금액', title="구매 목적별 매출 비중")
                st.plotly_chart(fig_purp, use_container_width=True)
        
        with col_g2:
            st.markdown("#### 상품 등급 (Premium)")
            if '상품성등급_그룹' in filtered_df.columns:
                fig_grade = px.pie(filtered_df, names='상품성등급_그룹', values='실결제 금액', title="등급별 매출 비중", hole=0.3)
                st.plotly_chart(fig_grade, use_container_width=True)
                
        with col_g3:
            st.markdown("#### 고액 취소 상품 (Risk)")
            cancel_df = filtered_df[filtered_df['주문취소 금액'] > 0]
            if not cancel_df.empty:
                top_cancel = cancel_df.groupby('상품명')['주문취소 금액'].sum().nlargest(5).reset_index()
            else:
                st.success("취소 내역이 없습니다.")
        
        st.markdown("---")
        
        # [NEW] Seller High-Margin Analysis (V7 Analysis)
        st.markdown("### 4. 셀러별 고수익 상품 포트폴리오 (New)")
        
        # Define High Margin: Above Overall Average Margin
        overall_margin = (filtered_df['이익'].sum() / filtered_df['실결제 금액'].sum() * 100)
        filtered_df['고수익_여부'] = filtered_df['이익률'] >= overall_margin
        
        # Analyze Top Sellers
        top_sellers_V7 = filtered_df.groupby('셀러명')['실결제 금액'].sum().nlargest(5).index
        
        portfolio_data = []
        for seller in top_sellers_V7:
            s_data = filtered_df[filtered_df['셀러명'] == seller]
            total_sales = s_data['실결제 금액'].sum()
            high_sales = s_data[s_data['고수익_여부']]['실결제 금액'].sum()
            ratio = (high_sales / total_sales * 100) if total_sales > 0 else 0
            
            # Top High Margin Product
            top_prod = s_data[s_data['고수익_여부']].groupby('상품명')['실결제 금액'].sum().nlargest(1)
            best_prod = top_prod.index[0] if not top_prod.empty else "없음"
            
            portfolio_data.append({
                '셀러명': seller,
                '고수익비중': ratio,
                '대표효자상품': best_prod
            })
            
        if portfolio_data:
            port_df = pd.DataFrame(portfolio_data).sort_values('고수익비중', ascending=False)
            
            col_p1, col_p2 = st.columns([2, 1])
            with col_p1:
                fig_port = px.bar(port_df, x='셀러명', y='고수익비중', color='고수익비중',
                                  title=f"상위 셀러의 고수익 상품 매출 비중 (기준: {overall_margin:.1f}% 이상)",
                                  text_auto='.1f', color_continuous_scale='Tealgrn')
                st.plotly_chart(fig_port, use_container_width=True)
            with col_p2:
                st.markdown("**🏆 셀러별 대표 효자 상품**")
                st.dataframe(port_df[['셀러명', '대표효자상품']], hide_index=True)

        st.markdown("---")

        # [NEW] Top 3 Region Analysis & Proposal (User Request)
        st.markdown("### 5. 핵심 지역(Top 3) 타겟팅 전략")
        if '광역지역(정식)' in filtered_df.columns:
            region_sales = filtered_df.groupby('광역지역(정식)')['실결제 금액'].sum().nlargest(3)
            top3_regions = region_sales.index.tolist()
            
            cols_r = st.columns(3)
            strategies = {
                '서울': "프리미엄 선물세트 및 당일 배송 서비스 강화",
                '경기': "가정용 대용량(5kg 이상) 패키지 및 묶음 배송 할인",
                '부산': "가성비 실속형 상품(소과/못난이) 기획전",
                '제주': "도민 할인 및 체험형 농장 연계 프로모션",
                '기타': "신규 고객 유치 쿠폰 발급"
            }
            
            for i, region in enumerate(top3_regions):
                with cols_r[i]:
                    r_data = filtered_df[filtered_df['광역지역(정식)'] == region]
                    r_sales = r_data['실결제 금액'].sum()
                    
                    # Top Product & Channel
                    top_prod = r_data.groupby('품종')['실결제 금액'].sum().nlargest(1).index[0]
                    top_ch = r_data.groupby('주문경로')['실결제 금액'].sum().nlargest(1).index[0]
                    
                    st.success(f"📍 **{i+1}위: {region}**")
                    st.metric("매출액", f"{r_sales:,.0f}원")
                    st.markdown(f"""
                    - **선호 품종**: {top_prod}
                    - **주력 채널**: {top_ch}
                    """)
                    
                    # Custom Strategy based on data
                    strategy = strategies.get(region, "지역 특화 프로모션 및 재구매 유도 캠페인")
                    st.info(f"💡 **제안**: {strategy}")

                    st.info(f"💡 **제안**: {strategy}")

        st.markdown("---")
        
        # [NEW] Top 5 Variety Analysis (User Request)
        st.markdown("### 6. 핵심 품종(Top 5) 성과 및 전략")
        if '품종' in filtered_df.columns:
            # Stats per Variety
            v_kpi = filtered_df.groupby('품종').agg({
                '실결제 금액': 'sum',
                '이익': 'sum',
                '주문번호': 'count',
                'UID': 'nunique'
            }).reset_index()
            
            # Derived Metrics
            v_kpi['이익률'] = (v_kpi['이익'] / v_kpi['실결제 금액'] * 100).fillna(0)
            v_kpi['재구매율'] = (v_kpi['주문번호'] / v_kpi['UID']).fillna(1.0)
            
            # [Chart] Revenue vs Profit (Top 10)
            st.markdown("#### 📊 품종별 매출 및 수익 비교 (Top 10)")
            top10_v = v_kpi.nlargest(10, '실결제 금액')
            
            # Reshape for Grouped Bar
            v_long = pd.melt(top10_v, id_vars=['품종'], value_vars=['실결제 금액', '이익'], 
                             var_name='지표', value_name='금액')
            
            fig_v_comp = px.bar(v_long, x='품종', y='금액', color='지표', barmode='group',
                                title="품종별 매출액(실결제) vs 수익(이익) 비교",
                                color_discrete_map={'실결제 금액': '#A8D5BA', '이익': '#2E8B57'})
            st.plotly_chart(fig_v_comp, use_container_width=True)

            # Top 5 Cards
            st.markdown("#### 🏆 핵심 품종(Top 5) 상세 전략")
            top5_v = v_kpi.nlargest(5, '실결제 금액')
            
            # Display Cards or Table
            cols_v = st.columns(5)
            
            for i, (_, row) in enumerate(top5_v.iterrows()):
                v_name = row['품종']
                revenue = row['실결제 금액']
                profit = row['이익']
                margin = row['이익률']
                repurchase = row['재구매율']
                
                # Dynamic Proposal
                if margin >= 40:
                    badge = "🌟 고수익"
                    proposal = "마케팅 예산 집중 (효자 상품)"
                elif repurchase >= 1.2:
                    badge = "❤️ 충성도"
                    proposal = "정기 배송/구독 서비스 제안"
                elif revenue > 10000000: # 1000만원 이상인데 마진 낮음
                    badge = "🔥 베스트셀러"
                    proposal = "원가 절감 및 묶음 판매 유도"
                else:
                    badge = "🥔 일반"
                    proposal = "재고 소진 프로모션"
                
                with cols_v[i]:
                    st.success(f"{i+1}위. {v_name} {badge}")
                    st.markdown(f"**매출**: {revenue/10000:,.0f}만")
                    st.markdown(f"**수익**: {profit/10000:,.0f}만")
                    st.metric("이익률", f"{margin:.1f}%", delta_color="normal" if margin>30 else "off")
                    st.metric("재구매지수", f"{repurchase:.2f}")
                    st.caption(f"💡 {proposal}")

        st.info("""
        **💡 경영 제안: 옴니채널 & Time & Location & Product 전략**
        - **지역 타겟팅**: Top 3 지역(수도권 등)에 맞춤형 배송/할인 정책을 적용하세요.
        - **품종 믹스**: 고이익 품종('황금향' 등)을 미끼 상품('감귤' 등)과 결합하여 객단가와 이익률을 동시에 잡으세요.
        """)

        # [NEW] Marketing Strategy Tab (User Request)
        with tab7:
            st.subheader("📈 마케팅 성과 및 전력 (Retention & Churn)")
            st.info("고객의 재구매를 유도하고 이탈을 방지하기 위한 셀러별 성과 분석 및 전략 제안 페이지입니다.")
            
            # 1. 셀러별 리텐션 지표 (재구매율 vs 이탈률)
            st.markdown("### 1. 셀러별 리텐션 현황")
            
            # Calculate metrics for the current filtered data
            seller_retention = filtered_df.groupby('셀러명').agg({
                'UID': 'nunique',
                '주문번호': 'count'
            }).rename(columns={'UID': '고유고객수', '주문번호': '총주문건수'})
            
            # Simple assumption: Reorder if orders > customers
            # But the preprocessed data has a '재구매 횟수' column which is more accurate
            if '재구매 횟수' in filtered_df.columns:
                reorder_data = filtered_df[filtered_df['재구매 횟수'] > 0].groupby('셀러명')['UID'].nunique()
                seller_retention['재구매고객수'] = reorder_data
                seller_retention['재구매고객수'] = seller_retention['재구매고객수'].fillna(0)
                seller_retention['재구매율(%)'] = (seller_retention['재구매고객수'] / seller_retention['고유고객수'] * 100).round(1)
            else:
                seller_retention['재구매율(%)'] = ((seller_retention['총주문건수'] - seller_retention['고유고객수']) / seller_retention['고유고객수'] * 100).round(1)
            
            seller_retention['이탈률(%)'] = (100 - seller_retention['재구매율(%)']).round(1)
            
            # Filter sellers with enough data
            min_cust = 5
            plot_retention = seller_retention[seller_retention['고유고객수'] >= min_cust].sort_values('재구매율(%)', ascending=False)
            
            if not plot_retention.empty:
                col_r1, col_r2 = st.columns([2, 1])
                with col_r1:
                    fig_reorder = px.bar(plot_retention.head(10).reset_index(), 
                                        x='셀러명', y='재구매율(%)', color='재구매율(%)',
                                        title=f"재구매율 상위 10개 셀러 (최소 고객 {min_cust}명 이상)",
                                        text_auto='.1f', color_continuous_scale='RdYlGn')
                    st.plotly_chart(fig_reorder, use_container_width=True)
                with col_r2:
                    st.markdown("**💡 분기점 분석 (Insight)**")
                    avg_reorder = seller_retention['재구매율(%)'].mean()
                    st.metric("평균 재구매율", f"{avg_reorder:.1f}%")
                    st.write(f"현재 상위 셀러들은 **{plot_retention['재구매율(%)'].max():.1f}%** 수준의 높은 리텐션을 보여주고 있습니다.")
            
            st.markdown("---")
            
            # 2. 경영 개선 방안 제안
            st.markdown("### 2. 재구매율 증가 및 이탈 방지 개선 방안")
            
            p_col1, p_col2 = st.columns(2)
            
            with p_col1:
                st.success("#### 🔄 재구매율(Retention) 강화 전략")
                st.markdown("""
                - **정기 구독 모델**: 감귤 등 주력 품종의 정기 배송 서비스 도입 (락인 효과)
                - **리워드 프로그램**: 재구매 횟수에 따른 차등 혜택(Silver/Gold/VIP) 제공
                - **CRM 자동화**: 예상 소비 주기 분석을 통한 구매 유도 알림톡/쿠폰 발송
                """)
                
            with p_col2:
                st.warning("#### 🛡️ 이탈률(Churn) 방어 전략")
                st.markdown("""
                - **첫 구매 Welcome Kit**: 1회 구매 고객 대상 '제주 스토리' 및 재구매 쿠폰 동봉
                - **품질 보상 제도**: 과일 파손/맛 이슈 발생 시 즉시 교환/환불 (신뢰 회복)
                - **가공품 라인업 확장**: 생과 외 가공식품(칩, 잼 등) 제공으로 비시즌 이탈 방지
                """)
            
            st.markdown("---")
            
            # 3. 고객 세그먼트 기여도 분석 (RFM)
            st.markdown("### 3. 고객 세그먼트별 매출 기여도")
            
            if os.path.exists('data/analysis/customer_rfm_segments.csv'):
                rfm_df = pd.read_csv('data/analysis/customer_rfm_segments.csv')
                
                col_s1, col_s2 = st.columns([1, 1])
                
                with col_s1:
                    segment_counts = rfm_df['Segment'].value_counts().reset_index()
                    fig_seg_count = px.pie(segment_counts, values='count', names='Segment', 
                                         title="세그먼트별 고객 수 분포",
                                         color_discrete_sequence=px.colors.qualitative.Pastel)
                    st.plotly_chart(fig_seg_count, use_container_width=True)
                    
                with col_s2:
                    segment_revenue = rfm_df.groupby('Segment')['Monetary'].sum().reset_index()
                    fig_seg_rev = px.pie(segment_revenue, values='Monetary', names='Segment', 
                                        title="세그먼트별 매출 기여도 (%)",
                                        hole=0.4,
                                        color_discrete_sequence=px.colors.qualitative.Safe)
                    st.plotly_chart(fig_seg_rev, use_container_width=True)
                    
                st.info("💡 **전략적 시사점**: VIP 및 우수 고객의 매출 기여도가 전체의 70% 이상일 경우, 기존 고객 유지를 위한 리텐션 마케팅에 예산을 우선 배정해야 합니다.")
            else:
                st.info("세그먼트 분석 데이터가 생성되지 않았습니다. 분석 스크립트를 먼저 실행해 주세요.")

            st.markdown("---")
            st.caption("※ 본 분석은 시니어 마케터의 경영 방향 제안을 포함하고 있습니다.")

        # [NEW] Comprehensive Report Tab
        with tab8:
            st.subheader("📋 종합 전략 보고서 및 AI 진단")
            st.info("작성된 마케팅 전략 및 EDA 분석 보고서를 대시보드에서 직접 확인하실 수 있습니다.")
            
            report_choice = st.selectbox("보고서 선택", 
                                        ["마케팅 전략 보고서 (2025)", "EDA 종합 분석 리포트", "전환율(CVR) 분석 보고서"])
            
            report_mapping = {
                "마케팅 전략 보고서 (2025)": "docs/analysis/marketing_strategy_report.md",
                "EDA 종합 분석 리포트": "docs/analysis/eda_comprehensive_report.md",
                "전환율(CVR) 분석 보고서": "docs/analysis/cvr_analysis_report.md"
            }
            
            report_path = report_mapping.get(report_choice)
            
            if report_path and os.path.exists(report_path):
                with open(report_path, 'r', encoding='utf-8') as f:
                    report_content = f.read()
                
                # 이미지 경로 처리 (Markdown에서 images/ -> docs/analysis/images/ 로 수정)
                report_content = report_content.replace('images/', 'docs/analysis/images/')
                
                st.markdown(report_content, unsafe_allow_html=True)
                
                st.download_button(
                    label="📄 보고서 다운로드 (Markdown)",
                    data=report_content,
                    file_name=os.path.basename(report_path),
                    mime="text/markdown"
                )
            else:
                st.warning(f"선택한 보고서 파일({report_path})을 찾을 수 없습니다.")

else:
    st.error("데이터 파일을 찾을 수 없습니다. 경로: 'data/preprocessed_data.csv'")
