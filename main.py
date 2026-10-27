import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from io import BytesIO


# ==========================================
# 1. 화면 설정
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
# 2. 공식 CSV 주소에서 자동 다운로드
# ==========================================
CSV_URL = (
    "https://www.data.go.kr/cmm/cmm/fileDownload.do"
    "?atchFileId=FILE_000000003517053"
    "&fileDetailSn=1"
    "&insertDataPrcus=N"
)


@st.cache_data(ttl=86400, show_spinner=False)
def load_public_data():
    """공공데이터포털에서 CSV를 자동으로 내려받습니다."""

    response = requests.get(
        CSV_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=120
    )

    response.raise_for_status()

    if not response.content:
        raise ValueError("다운로드한 파일이 비어 있습니다.")

    # 오류 페이지나 로그인 페이지가 CSV 대신 반환되는 경우 확인
    content = response.content
    preview = content[:500].lstrip(b"\xef\xbb\xbf \r\n\t").lower()
    content_type = response.headers.get("Content-Type", "").lower()

    if (
        "text/html" in content_type
        or preview.startswith(b"<!doctype html")
        or preview.startswith(b"<html")
    ):
        raise ValueError(
            "CSV 대신 웹페이지가 반환되었습니다. "
            "공식 데이터 다운로드 주소가 변경되었는지 확인해 주세요."
        )

    # 한글 CSV의 인코딩 차이에 대응
    for encoding in ["utf-8-sig", "cp949", "euc-kr"]:
        try:
            df = pd.read_csv(
                BytesIO(content),
                encoding=encoding
            )
            df.columns = df.columns.astype(str).str.strip()
            return df

        except UnicodeDecodeError:
            continue

    raise ValueError("CSV 파일의 문자 인코딩을 확인할 수 없습니다.")


with st.spinner("공식 상권 데이터를 다운로드하고 있습니다..."):
    try:
        df = load_public_data()
        st.success("공식 데이터를 자동으로 불러왔습니다.")

    except Exception as e:
        st.error("공식 CSV 데이터를 불러오지 못했습니다.")
        st.write("잠시 후 다시 실행하거나 데이터 다운로드 주소를 확인하세요.")
        st.code(str(e))
        st.link_button(
            "공식 데이터 페이지 열기",
            "https://www.data.go.kr/data/15150337/fileData.do?recommendDataYn=Y"
        )
        st.stop()


# ==========================================
# 3. 데이터 확인 및 정리
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
    col for col in required_columns
    if col not in df.columns
]

if missing_columns:
    st.error(
        "CSV 파일의 컬럼 구성이 예상과 다릅니다: "
        + ", ".join(missing_columns)
    )
    st.write("실제로 다운로드한 CSV의 컬럼 목록:")
    st.write(df.columns.tolist())
    st.stop()

df = df[required_columns].copy()

text_columns = [
    "시도명",
    "시군구명",
    "행정동명",
    "업종명"
]

for col in text_columns:
    df[col] = df[col].astype("string").str.strip()

df = df.dropna(subset=text_columns)

for col in text_columns:
    df = df[df[col].str.len() > 0]

quarter_columns = ["1분기", "2분기", "3분기", "4분기"]

for col in quarter_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")
    df.loc[df[col] < 0, col] = float("nan")

df = df.dropna(subset=quarter_columns, how="all")
df[quarter_columns] = df[quarter_columns].fillna(0)

if df.empty:
    st.error("분석할 데이터가 없습니다.")
    st.stop()

st.caption(
    f"분석 데이터: {len(df):,}행 · "
    f"{df['업종명'].nunique():,}개 업종"
)


# ==========================================
# 4. 시도 → 시군구 → 동 선택
# ==========================================
st.subheader("📍 분석할 지역 선택")

col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df["시도명"].unique().tolist())
    selected_sido = st.selectbox(
        "1. 시도",
        sido_list
    )

sido_df = df[df["시도명"] == selected_sido]

with col2:
    sigungu_list = sorted(
        sido_df["시군구명"].unique().tolist()
    )
    selected_sigungu = st.selectbox(
        "2. 시군구",
        sigungu_list
    )

sigungu_df = sido_df[
    sido_df["시군구명"] == selected_sigungu
]

with col3:
    dong_list = sorted(
        sigungu_df["행정동명"].unique().tolist()
    )
    selected_dong = st.selectbox(
        "3. 동",
        dong_list
    )

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
st.subheader("📅 분석 기준")

selected_quarter = st.selectbox(
    "분기 선택",
    quarter_columns,
    index=3
)


# ==========================================
# 6. 업종별 업소 수 계산
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
    st.warning("선택한 지역에 분석할 업종이 없습니다.")
    st.stop()

industry_df["업소 수"] = industry_df["업소 수"].astype(int)

total_stores = int(industry_df["업소 수"].sum())
industry_count = len(industry_df)

top_row = industry_df.iloc[0]
top_industry = str(top_row["업종명"])
top_count = int(top_row["업소 수"])

top_share = (
    top_count / total_stores * 100
    if total_stores > 0 else 0
)


# ==========================================
# 7. 핵심 지표
# ==========================================
st.divider()
st.subheader("📊 핵심 상권 지표")

metric1, metric2, metric3 = st.columns(3)

metric1.metric(
    "총 업소 수",
    f"{total_stores:,}개"
)

metric2.metric(
    "분석 업종 수",
    f"{industry_count:,}개"
)

metric3.metric(
    "업소 수 1위 업종",
    top_industry
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
    }
)

fig.update_traces(
    texttemplate="%{text:,}",
    textposition="outside",
    cliponaxis=False
)

fig.update_layout(
    height=max(420, len(chart_df) * 35),
    margin=dict(l=20, r=60, t=60, b=20),
    xaxis_title="업소 수(개)",
    yaxis_title="업종"
)

st.plotly_chart(fig, use_container_width=True)


# ==========================================
# 9. 업종별 분기 변화
# ==========================================
st.divider()
st.subheader("📉 업종별 분기 변화")

trend_industries = sorted(
    area_df["업종명"].unique().tolist()
)

default_index = trend_industries.index(top_industry)

selected_industry = st.selectbox(
    "분기별 변화를 확인할 업종",
    trend_industries,
    index=default_index
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
    title=f"{selected_industry} 분기별 업소 수",
    labels={
        "분기": "분기",
        "업소 수": "업소 수(개)"
    }
)

quarter_fig.update_layout(height=380)

st.plotly_chart(
    quarter_fig,
    use_container_width=True
)

first_value = int(quarter_totals.iloc[0]["업소 수"])
last_value = int(quarter_totals.iloc[-1]["업소 수"])

if first_value > 0:
    change_rate = (last_value - first_value) / first_value * 100

    if change_rate > 0:
        st.info(
            f"{selected_industry}의 4분기 업소 수는 "
            f"1분기보다 {change_rate:.1f}% 많습니다."
        )
    elif change_rate < 0:
        st.info(
            f"{selected_industry}의 4분기 업소 수는 "
            f"1분기보다 {abs(change_rate):.1f}% 적습니다."
        )
    else:
        st.info(
            f"{selected_industry}의 1분기와 4분기 업소 수는 같습니다."
        )
else:
    st.info(
        "1분기 업소 수가 0개이므로 변화율을 계산할 수 없습니다."
    )


# ==========================================
# 10. 창업 의사결정 참고
# ==========================================
st.divider()
st.subheader("💡 창업 의사결정 참고")

st.write(
    f"선택한 지역에서 {selected_quarter} 기준 "
    f"업소 수가 가장 많은 업종은 **{top_industry}**이며, "
    f"업소 수는 **{top_count:,}개**입니다."
)

st.write(
    "업소 수가 많은 업종은 경쟁 점포가 많을 수 있지만 "
    "고객 수요도 존재할 수 있습니다. 반대로 업소 수가 적다는 "
    "사실만으로 새로운 창업 기회라고 단정할 수 없습니다."
)

st.write(
    "창업 전에는 유동인구, 고객 특성, 임대료, 매출 자료, "
    "주변 경쟁 점포의 위치 등을 추가로 확인하는 것이 좋습니다."
)

st.warning(
    "데이터 한계: 이 자료는 합성데이터이며 실제 매출액이나 "
    "순이익을 나타내지 않습니다. 업소 수만으로 창업 성공 여부를 "
    "예측할 수 없습니다."
)


# ==========================================
# 11. 상세 데이터 및 CSV 다운로드
# ==========================================
st.divider()
st.subheader("📋 업종별 상세 데이터")

with st.expander("업종별 업소 수 표 보기"):
    st.dataframe(
        industry_df,
        use_container_width=True,
        hide_index=True
    )

csv_data = industry_df.to_csv(
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
st.subheader("📚 데이터 출처")

st.markdown(
    """
    - **제공기관:** 소상공인시장진흥공단
    - **데이터명:** 부산광역시 소상공인 업소 통계정보 합성데이터
    - **공식 페이지:**
      https://www.data.go.kr/data/15150337/fileData.do?recommendDataYn=Y
    - **주요 항목:** 시도명, 시군구명, 행정동명, 업종명, 분기별 업소 수
    """
)
