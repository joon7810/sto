
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="상권 분석 및 창업 도우미",
    page_icon="🏪",
    layout="wide"
)

st.title("🏪 공공데이터 기반 상권 분석 및 창업 의사결정")
st.write(
    "지역별 업종 분포와 분기별 업소 수를 비교하여 "
    "창업 후보 지역을 검토하는 프로그램입니다."
)

st.info(
    "자료 안내: 소상공인시장진흥공단의 부산광역시 "
    "소상공인 업소 통계정보 합성데이터를 사용합니다. "
    "실제 매출이나 개별 가게의 수익을 나타내는 자료는 아닙니다."
)

# 1. CSV 파일 불러오기
st.subheader("1. 데이터 불러오기")

file_path = Path("small_business_stats.csv")

if file_path.exists():
    try:
        df = pd.read_csv(file_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(file_path, encoding="cp949")
    st.success("프로젝트의 CSV 파일을 불러왔습니다.")
else:
    uploaded_file = st.file_uploader(
        "공식 데이터 CSV 파일을 선택하세요.",
        type=["csv"]
    )

    if uploaded_file is None:
        st.warning(
            "CSV 파일을 프로젝트 폴더에 넣거나 "
            "위에서 파일을 업로드해 주세요."
        )
        st.stop()

    try:
        df = pd.read_csv(uploaded_file, encoding="utf-8-sig")
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, encoding="cp949")

# 컬럼명 앞뒤 공백 제거
df.columns = df.columns.astype(str).str.strip()

# 2. 필수 컬럼 확인
required_columns = [
    "시도명", "시군구명", "행정동명", "업종명",
    "1분기", "2분기", "3분기", "4분기"
]

missing_columns = [
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    st.error(
        "CSV 파일의 컬럼 구성이 예상과 다릅니다: "
        + ", ".join(missing_columns)
    )
    st.write("실제 컬럼:", list(df.columns))
    st.stop()

# 3. 데이터 정리
df = df[required_columns].copy()

for col in ["시도명", "시군구명", "행정동명", "업종명"]:
    df[col] = df[col].astype("string").str.strip()

quarter_columns = ["1분기", "2분기", "3분기", "4분기"]

for col in quarter_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df.dropna(
    subset=["시도명", "시군구명", "행정동명", "업종명"]
)

df = df.dropna(subset=quarter_columns, how="all")
df[quarter_columns] = df[quarter_columns].fillna(0)

# 음수 업소 수는 잘못된 값으로 처리
for col in quarter_columns:
    df.loc[df[col] < 0, col] = 0

if df.empty:
    st.error("분석할 수 있는 데이터가 없습니다.")
    st.stop()

st.caption(f"분석에 사용할 데이터 행 수: {len(df):,}개")

# 4. 지역 선택
st.subheader("2. 창업 후보 지역 선택")

col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df["시도명"].dropna().unique().tolist())
    selected_sido = st.selectbox("시도", sido_list)

sido_df = df[df["시도명"] == selected_sido]

with col2:
    sigungu_list = sorted(
        sido_df["시군구명"].dropna().unique().tolist()
    )
    selected_sigungu = st.selectbox("시군구", sigungu_list)

sigungu_df = sido_df[
    sido_df["시군구명"] == selected_sigungu
]

with col3:
    dong_list = sorted(
        sigungu_df["행정동명"].dropna().unique().tolist()
    )
    selected_dong = st.selectbox("행정동", dong_list)

dong_df = sigungu_df[
    sigungu_df["행정동명"] == selected_dong
].copy()

# 5. 분기 선택
selected_quarter = st.selectbox(
    "분석할 분기",
    quarter_columns
)

# 6. 선택한 지역의 업종별 통계
st.divider()
st.subheader("3. 선택 지역의 상권 현황")

industry_df = (
    dong_df.groupby("업종명", as_index=False)[quarter_columns]
    .sum()
)

industry_df["선택 분기 업소 수"] = industry_df[
    selected_quarter
]

industry_df = industry_df.sort_values(
    "선택 분기 업소 수",
    ascending=False
)

total_businesses = industry_df[
    "선택 분기 업소 수"
].sum()

if industry_df.empty:
    st.warning("선택한 지역의 업종 데이터가 없습니다.")
    st.stop()

top_industry = industry_df.iloc[0]["업종명"]
top_count = industry_df.iloc[0]["선택 분기 업소 수"]

m1, m2, m3 = st.columns(3)

m1.metric("선택 지역", selected_dong)
m2.metric(
    f"{selected_quarter} 업소 수 합계",
    f"{total_businesses:,.0f}개"
)
m3.metric(
    "업소 수가 가장 많은 업종",
    str(top_industry),
    delta=f"{top_count:,.0f}개"
)

# 7. 업종별 업소 수 그래프
st.subheader("4. 업종별 경쟁 환경 비교")

top_n = st.slider(
    "그래프에 표시할 업종 수",
    min_value=3,
    max_value=min(20, len(industry_df)),
    value=min(10, len(industry_df))
)

chart_df = industry_df.head(top_n).sort_values(
    "선택 분기 업소 수"
)

fig = px.bar(
    chart_df,
    x="선택 분기 업소 수",
    y="업종명",
    orientation="h",
    title=f"{selected_dong} 업종별 업소 수",
    labels={
        "선택 분기 업소 수": "업소 수",
        "업종명": "업종"
    }
)

st.plotly_chart(fig, use_container_width=True)

# 8. 특정 업종의 분기별 변화
st.divider()
st.subheader("5. 업종별 분기 변화 분석")

industry_options = sorted(
    dong_df["업종명"].dropna().unique().tolist()
)

selected_industry = st.selectbox(
    "분석할 창업 업종",
    industry_options
)

selected_data = dong_df[
    dong_df["업종명"] == selected_industry
]

quarter_totals = selected_data[
    quarter_columns
].sum()

trend_df = pd.DataFrame({
    "분기": quarter_columns,
    "업소 수": quarter_totals.values
})

fig_trend = px.line(
    trend_df,
    x="분기",
    y="업소 수",
    markers=True,
    title=f"{selected_dong} - {selected_industry} 분기별 업소 수"
)

st.plotly_chart(fig_trend, use_container_width=True)

# 9. 창업 의사결정 참고
st.divider()
st.subheader("6. 창업 의사결정 참고")

industry_count = float(
    quarter_totals.get(selected_quarter, 0)
)

st.write(
    f"선택한 지역은 **{selected_dong}**, "
    f"관심 업종은 **{selected_industry}**입니다."
)

st.write(
    f"선택한 분기의 해당 업종 통계는 "
    f"**{industry_count:,.0f}개**입니다."
)

if industry_count == 0:
    st.warning(
        "선택한 분기에 해당 업종의 업소 수가 0으로 집계되었습니다. "
        "다른 지역이나 업종도 비교해 보세요."
    )
else:
    st.info(
        "업소 수가 많다는 것은 해당 업종의 경쟁자가 많을 가능성을 "
        "보여 줍니다. 하지만 수요가 많을 수도 있으므로 "
        "업소 수만으로 창업 성공 여부를 판단할 수는 없습니다."
    )

# 10. 자료 미리보기 및 다운로드
with st.expander("분석 데이터 확인하기"):
    st.dataframe(df, use_container_width=True)

st.download_button(
    label="선택 지역의 분석 결과 CSV 다운로드",
    data=industry_df.to_csv(index=False).encode("utf-8-sig"),
    file_name="상권_분석결과.csv",
    mime="text/csv"
)

st.caption(
    "출처: 소상공인시장진흥공단, "
    "부산광역시 소상공인 업소 통계정보 합성데이터. "
    "본 분석은 참고용이며 실제 매출이나 창업 성공을 보장하지 않습니다."
)
