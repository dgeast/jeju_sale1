import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os

# 시각화 한글 폰트 설정 (Windows 기준)
from matplotlib import font_manager, rc
font_path = "C:/Windows/Fonts/malgun.ttf"
if os.path.exists(font_path):
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    rc('font', family=font_name)
else:
    print("Warning: Malgun Gothic font not found. Using default font.")
plt.rcParams['axes.unicode_minus'] = False

# 데이터 로드
try:
    df_sales = pd.read_csv('data/preprocessed_data_1.csv')
    # Click과 Visit 데이터는 구조가 다를 수 있으므로 에러 무시하고 진행
    try:
        df_click = pd.read_csv('data/salesclick_1.csv')
    except:
        df_click = pd.DataFrame()
    try:
        df_visit = pd.read_csv('data/salesvisit_1.csv')
    except:
        df_visit = pd.DataFrame()
    print("데이터 로드 완료")
except Exception as e:
    print(f"데이터 로드 중 오류 발생: {e}")
    exit()

# 출력 디렉토리 생성
if not os.path.exists('docs/analysis/images'):
    os.makedirs('docs/analysis/images')
if not os.path.exists('data/analysis'):
    os.makedirs('data/analysis')

# 컬럼명 매핑 (데이터 확인 결과 반영)
SELLER_COL = '셀러명'
CHANNEL_COL = '주문경로'
REGION_COL = '광역지역(정식)'
UID_COL = 'UID'
SALES_COL = '결제금액'
ORDER_ID_COL = '주문번호'

# 1. 셀러별 성과 분석
# 고객별 주문 통계
customer_stats = df_sales.groupby([SELLER_COL, UID_COL]).agg({
    ORDER_ID_COL: 'count',
    SALES_COL: 'sum'
}).reset_index().rename(columns={ORDER_ID_COL: 'order_count', SALES_COL: 'customer_total_sales'})

# 재구매 횟수 (주문건수 - 1)
customer_stats['reorder_count'] = customer_stats['order_count'] - 1

# 셀러별 지표 집계
seller_metrics = df_sales.groupby(SELLER_COL).agg({
    SALES_COL: 'sum',
    ORDER_ID_COL: 'count',
    UID_COL: 'nunique'
}).rename(columns={SALES_COL: 'total_sales', ORDER_ID_COL: 'total_orders', UID_COL: 'unique_customers'})

# 재구매 관련 성과
reorder_summary = customer_stats[customer_stats['reorder_count'] > 0].groupby(SELLER_COL).agg({
    UID_COL: 'count',
    'reorder_count': 'sum'
}).rename(columns={UID_COL: 'reordering_customers', 'reorder_count': 'total_reorders'})

seller_metrics = seller_metrics.join(reorder_summary).fillna(0)
seller_metrics['reorder_rate'] = (seller_metrics['reordering_customers'] / seller_metrics['unique_customers']) * 100
seller_metrics['churn_rate'] = (1 - (seller_metrics['reordering_customers'] / seller_metrics['unique_customers'])) * 100

# 2. 유입채널 및 지역별 분석
if CHANNEL_COL in df_sales.columns:
    channel_analysis = df_sales.groupby(CHANNEL_COL).agg({
        SALES_COL: 'sum',
        ORDER_ID_COL: 'count'
    }).sort_values(by=SALES_COL, ascending=False)
    channel_analysis.to_csv('data/analysis/channel_analysis.csv')

if REGION_COL in df_sales.columns:
    region_analysis = df_sales.groupby(REGION_COL).agg({
        SALES_COL: 'sum',
        ORDER_ID_COL: 'count'
    }).sort_values(by=SALES_COL, ascending=False)
    region_analysis.to_csv('data/analysis/region_analysis.csv')

# 3. 시각화
# 셀러별 매출 Top 10
plt.figure(figsize=(12, 6))
top_10_sales = seller_metrics.sort_values(by='total_sales', ascending=False).head(10)
sns.barplot(x=top_10_sales.index, y=top_10_sales['total_sales'], palette='viridis')
plt.title('상위 10개 셀러별 매출 현황', fontsize=15)
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig('docs/analysis/images/seller_sales_top10.png')

# 셀러별 재구매율 Top 10
plt.figure(figsize=(12, 6))
# 고객이 최소 5명 이상인 셀러 대상
top_10_reorder = seller_metrics[seller_metrics['unique_customers'] >= 5].sort_values(by='reorder_rate', ascending=False).head(10)
if not top_10_reorder.empty:
    sns.barplot(x=top_10_reorder.index, y=top_10_reorder['reorder_rate'], palette='magma')
    plt.title('재구매율 상위 10개 셀러 (고객 5명 이상 기준)', fontsize=15)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('docs/analysis/images/seller_reorder_top10.png')

# 4. 결과 저장
seller_metrics.to_csv('data/analysis/seller_comprehensive_metrics.csv')
print("분석 완료 및 파일 저장 성공")
