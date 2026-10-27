import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# ==========================================
# 1. 기본 화면 설정
# ==========================================
st.set_page_config(
    page_title="공공데이터 기반 상권 분석",
    page_icon="🏪",
    layout="wide"
)

st.title("🏪 공공데이터 기반 상권 분석")
st.write(
    "지역별 소상공인 업종 분포를 비교하고 "
    "창업 아이템을 탐색하는 프로그램입니다."
)

st.caption(
    "데이터 출처: 소상공인시장진흥공단 · "
    "부산광역시 소상공인 업소 통계정보 합성데이터"
)

st.divider()


# ==========================================
# 2. CSV 파일 불러오기
# ==========================================
@st.cache_data
def load_csv(file_source):
    """CSV 파일을 읽고 컬럼과 숫자 데이터를 정리합니다."""
    try:
        df = pd.read_csv(file_source, encoding="utf-8-sig")
    except UnicodeDecodeError:
        file_source.seek(0) if hasattr(file_source, "seek") else None
        df = pd.read_csv(file_source, encoding="cp949")

    # 컬럼명 앞뒤 공백 제거
    df.columns = df.columns.astype(str).str.strip()

    return df


csv_path = Path("small_business_stats.csv")

if csv_path.exists():
    try:
        df = load_csv(csv_path)
        st.success("저장된 공식 CSV 파일을 불러왔습니다.")
    except Exception as e:
        st.error(f"CSV 파일을 읽는 중 오류가 발생했습니다: {e}")
        st.stop()
else:
    st.info(
        "GitHub에 small_business_stats.csv 파일을 올리거나, "
        "아래에서 CSV 파일을 업로드하세요."
    )

    uploaded_file = st.file_uploader(
        "소상공인 업소 통계 CSV 파일 선택",
        type=["csv"]
    )

    if uploaded_file is None:
        st.stop()

    try:
        df = load_csv(uploaded_file)
    except Exception as e:
        st.error(f"CSV 파일을 읽을 수 없습니다: {e}")
        st.stop()


# ==========================================
# 3. 데이터 확인 및 전처리
# ==========================================
required_columns = [
    "시도명",
    "시군구명",
    "행정동명",
    "업종명",
    "1분기",
    "2분기",
    "3분기",
    "4분기"
]

missing_columns = [
    column for column in required_columns
    if column not in df.columns
]

if missing_columns:
    st.error(
        "CSV 파일에 필요한 컬럼이 없습니다: "
        + ", ".join(missing_columns)
    )
    st.write("현재 CSV 파일의 컬럼 목록")
    st.write(df.columns.tolist())
    st.info(
        "공식 데이터의 컬럼명과 같은 파일인지 확인해 주세요."
    )
    st.stop()

# 필요한 컬럼만 사용
df = df[required_columns].copy()

# 문자 데이터 정리
text_columns = [
    "시도명",
    "시군구명",
    "행정동명",
    "업종명"
]

for column in text_columns:
    df[column] = df[column].astype("string").str.strip()

# 숫자 데이터 변환
quarter_columns = ["1분기", "2분기", "3분기", "4분기"]

for column in quarter_columns:
    df[column] = pd.to_numeric(df[column], errors="coerce")

# 필수 정보가 없는 행 제거
df = df.dropna(subset=text_columns)

# 빈 문자열 제거
for column in text_columns:
    df = df[df[column].str.len() > 0]

if df.empty:
    st.error("분석할 데이터가 없습니다.")
    st.stop()

# 음수 업소 수는 분석에서 제외
for column in quarter_columns:
    df.loc[df[column] < 0, column] = float("nan")

# 네 분기 값이 모두 비어 있는 행은 제외
df = df.dropna(subset=quarter_columns, how="all")

if df.empty:
    st.error("분기별 업소 수 데이터가 없습니다.")
    st.stop()

# 결측 분기 값은 계산 시 0으로 처리
df[quarter_columns] = df[quarter_columns].fillna(0)

# 데이터 규모 표시
st.caption(
    f"분석 가능한 데이터: {len(df):,}개 행 · "
    f"{df['업종명'].nunique():,}개 업종"
)


# ==========================================
# 4. 지역 선택: 시도 → 시군구 → 동
# ==========================================
st.subheader("📍 분석할 지역 선택")

col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df["시도명"].unique().tolist())
    selected_sido = st.selectbox(
        "1. 시도 선택",
        sido_list
    )

# 선택한 시도에 속한 시군구만 표시
sido_df = df[df["시도명"] == selected_sido]

with col2:
    sigungu_list = sorted(
        sido_df["시군구명"].unique().tolist()
    )
    selected_sigungu = st.selectbox(
        "2. 시군구 선택",
        sigungu_list
    )

# 선택한 시군구에 속한 동만 표시
sigungu_df = sido_df[
    sido_df["시군구명"] == selected_sigungu
]

with col3:
    dong_list = sorted(
        sigungu_df["행정동명"].unique().tolist()
    )
    selected_dong = st.selectbox(
        "3. 동 선택",
        dong_list
    )

# 최종 선택 지역 데이터
area_df = sigungu_df[
    sigungu_df["행정동명"] == selected_dong
].copy()

st.write(
    f"**선택한 지역:** {selected_sido} "
    f"{selected_sigungu} {selected_dong}"
)


# ==========================================
# 5. 분석 분기 선택
# ==========================================
st.subheader("📅 분석 기준 선택")

selected_quarter = st.selectbox(
    "분기 선택",
    quarter_columns,
    index=3
)

st.caption(
    f"현재 분석은 선택한 지역의 {selected_quarter} 업소 수를 기준으로 합니다."
)


# ==========================================
# 6. 업종별 통계 계산
# ==========================================
industry_df = (
    area_df.groupby("업종명", as_index=False)[selected_quarter]
    .sum()
    .rename(columns={selected_quarter: "업소 수"})
)

industry_df = industry_df.sort_values(
    "업소 수",
    ascending=False
).reset_index(drop=True)

if industry_df.empty:
    st.warning("선택한 지역에서 분석할 업종이 없습니다.")
    st.stop()

total_stores = int(industry_df["업소 수"].sum())
industry_count = len(industry_df)

# 업소 수가 가장 많은 업종
top_row = industry_df.iloc[0]
top_industry = str(top_row["업종명"])
top_count = int(top_row["업소 수"])

# 전체 업소 수 중 1위 업종의 비중
if total_stores > 0:
    top_share = top_count / total_stores * 100
else:
    top_share = 0


# ==========================================
# 7. 핵심 지표 카드
# ==========================================
st.divider()
st.subheader("📊 핵심 상권 지표")

metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric(
        label="총 업소 수",
        value=f"{total_stores:,}개"
    )

with metric2:
    st.metric(
        label="분석 업종 수",
        value=f"{industry_count:,}개"
    )

with metric3:
    st.metric(
        label="업소 수 1위 업종",
        value=top_industry,
        help="선택한 분기에서 업소 수가 가장 많은 업종입니다."
    )

st.write(
    f"**1위 업종 업소 수:** {top_count:,}개 "
    f"({top_share:.1f}%)"
)


# ==========================================
# 8. 업종별 업소 수 막대그래프
# ==========================================
st.divider()
st.subheader("📈 업종별 업소 수 비교")

max_industries = st.slider(
    "그래프에 표시할 업종 수",
    min_value=5,
    max_value=30,
    value=10,
    step=5
)

chart_df = industry_df.head(max_industries).copy()
chart_df = chart_df.sort_values("업소 수", ascending=True)

fig = px.bar(
    chart_df,
    x="업소 수",
    y="업종명",
    orientation="h",
    text="업소 수",
    title=f"{selected_dong} 업종별 업소 수 ({selected_quarter})",
    labels={
        "업소 수": "업소 수(개)",
        "업종명": "업종"
    },
    hover_data={"업소 수": ":,"}
)

fig.update_traces(
    texttemplate="%{text:,}",
    textposition="outside",
    cliponaxis=False
)

fig.update_layout(
    yaxis_title="업종",
    xaxis_title="업소 수(개)",
    height=max(420, len(chart_df) * 35),
    margin=dict(l=20, r=60, t=60, b=20)
)

st.plotly_chart(fig, use_container_width=True)


# ==========================================
# 9. 분기별 업소 수 변화 분석
# ==========================================
st.divider()
st.subheader("📉 업종별 분기 변화")

trend_industries = sorted(
    area_df["업종명"].unique().tolist()
)

default_industry = top_industry

selected_industry = st.selectbox(
    "분기별 변화를 확인할 업종",
    trend_industries,
    index=trend_industries.index(default_industry)
)

trend_df = area_df[
    area_df["업종명"] == selected_industry
]

quarter_totals = (
    trend_df[quarter_columns]
    .sum()
    .reset_index()
)

quarter_totals.columns = ["분기", "업소 수"]

quarter_fig = px.line(
    quarter_totals,
    x="분기",
    y="업소 수",
    markers=True,
    title=f"{selected_industry} 업소 수의 분기별 변화",
    labels={
        "분기": "분기",
        "업소 수": "업소 수(개)"
    }
)

quarter_fig.update_traces(
    line=dict(width=3),
    marker=dict(size=9)
)

quarter_fig.update_layout(
    height=380,
    xaxis_title="분기",
    yaxis_title="업소 수(개)"
)

st.plotly_chart(
    quarter_fig,
    use_container_width=True
)

# 선택 업종의 첫 분기와 마지막 분기 비교
first_value = int(quarter_totals.iloc[0]["업소 수"])
last_value = int(quarter_totals.iloc[-1]["업소 수"])

if first_value > 0:
    change_rate = (last_value - first_value) / first_value * 100
else:
    change_rate = None

if change_rate is not None:
    if change_rate > 0:
        st.info(
            f"분기별 집계 기준으로 {selected_industry} 업소 수는 "
            f"1분기 대비 4분기에 {change_rate:.1f}% 많습니다."
        )
    elif change_rate < 0:
        st.info(
            f"분기별 집계 기준으로 {selected_industry} 업소 수는 "
            f"1분기 대비 4분기에 {abs(change_rate):.1f}% 적습니다."
        )
    else:
        st.info(
            f"{selected_industry} 업소 수는 1분기와 4분기가 같습니다."
        )
else:
    st.info(
        f"{selected_industry} 업종은 1분기 업소 수가 0개이므로 "
        "변화율을 계산하지 않았습니다."
    )


# ==========================================
# 10. 창업 아이템 탐색 참고
# ==========================================
st.divider()
st.subheader("💡 창업 의사결정 참고")

st.write(
    f"현재 선택한 지역에서 {selected_quarter} 기준으로 "
    f"업소 수가 가장 많은 업종은 **{top_industry}**이며, "
    f"집계된 업소 수는 **{top_count:,}개**입니다."
)

st.write(
    "업소 수가 많은 업종은 경쟁 점포가 많을 가능성이 있지만, "
    "동시에 고객 수요가 존재할 가능성도 있습니다. "
    "반대로 업소 수가 적은 업종도 수요가 적어서일 수 있으므로 "
    "업소 수만으로 창업 성공 여부를 판단할 수 없습니다."
)

st.write(
    "실제 창업 전에는 유동인구, 고객 특성, 임대료, 매출, "
    "주변 경쟁 점포의 위치와 운영 상황 등을 추가로 확인하세요."
)

st.warning(
    "주의: 이 데이터는 합성데이터이며, 실제 점포의 매출이나 "
    "순이익을 나타내지 않습니다. 분기별 값도 실제 폐업·개업을 "
    "직접 증명하는 정보가 아니므로 참고용으로 활용하세요."
)


# ==========================================
# 11. 업종별 상세 데이터와 다운로드
# ==========================================
st.divider()
st.subheader("📋 업종별 상세 데이터")

with st.expander("선택한 지역의 업종별 업소 수 보기"):
    display_df = industry_df.copy()
    display_df["업소 수"] = display_df["업소 수"].astype(int)

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

# CSV 다운로드용 파일 생성
download_df = industry_df.copy()
download_df["업소 수"] = download_df["업소 수"].astype(int)

csv_data = download_df.to_csv(
    index=False,
    encoding="utf-8-sig"
).encode("utf-8-sig")

st.download_button(
    label="📥 분석 결과 CSV 다운로드",
    data=csv_data,
    file_name=f"{selected_dong}_{selected_quarter}_업종분석.csv",
    mime="text/csv"
)


# ==========================================
# 12. 데이터 출처
# ==========================================
st.divider()
st.subheader("📚 데이터 출처 및 한계")

st.markdown(
    """
    - **제공기관:** 소상공인시장진흥공단
    - **데이터명:** 부산광역시 소상공인 업소 통계정보 합성데이터
    - **공식 다운로드 페이지:**  
      https://www.data.go.kr/data/15150337/fileData.do?recommendDataYn=Y
    - **주요 컬럼:** 시도명, 시군구명, 행정동명, 업종명, 1분기, 2분기, 3분기, 4분기
    - **활용 목적:** 지역별 업종 분포 비교 및 창업 아이템 탐색
    - **한계:** 합성데이터이므로 실제 매출, 이익, 창업 성공 가능성을 직접 보여주지 않습니다.
    """
)

st.caption(
    "공공데이터를 활용한 상권 탐색 프로그램 · "
    "분석 결과는 창업 의사결정을 위한 참고 자료입니다."
)
