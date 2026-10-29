import os
import re
import tempfile
import zipfile

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# ==========================================
# 1. 기본 설정
# ==========================================
st.set_page_config(
    page_title="전국 상권 분석",
    page_icon="🏪",
    layout="wide"
)

st.title("🏪 전국 상권 분석 및 창업 의사결정")
st.write(
    "전국의 지역별 상가와 업종 분포를 분석해 "
    "창업 아이템을 탐색하는 프로그램입니다."
)

st.caption(
    "데이터 제공기관: 소상공인시장진흥공단 | "
    "자료 기준일: 2026년 3월 31일"
)


# ==========================================
# 2. 전국 데이터 다운로드 주소
# ==========================================
# 공식 공공데이터포털에 등록된 ZIP 파일의 직접 다운로드 주소
DATA_URL = (
    "https://www.data.go.kr/cmm/cmm/fileDownload.do"
    "?atchFileId=FILE_000000003632420"
    "&fileDetailSn=1"
    "&insertDataPrcus=N"
)

DATA_PAGE_URL = "https://www.data.go.kr/data/15083033/fileData.do"


# 전국 17개 시·도와 ZIP 내부 파일명의 지역 코드
REGIONS = {
    "강원특별자치도": "강원",
    "경기도": "경기",
    "경상남도": "경남",
    "경상북도": "경북",
    "광주광역시": "광주",
    "대구광역시": "대구",
    "대전광역시": "대전",
    "부산광역시": "부산",
    "서울특별시": "서울",
    "세종특별자치시": "세종",
    "울산광역시": "울산",
    "인천광역시": "인천",
    "전라남도": "전남",
    "전북특별자치도": "전북",
    "제주특별자치도": "제주",
    "충청남도": "충남",
    "충청북도": "충북",
}

REGION_NAMES = list(REGIONS.keys())


# ==========================================
# 3. ZIP 파일 자동 다운로드
# ==========================================
@st.cache_resource(show_spinner=False)
def download_zip_to_disk():
    """
    공식 데이터 ZIP 파일을 임시 디스크에 저장합니다.
    전체 파일을 메모리에 한꺼번에 올리지 않습니다.
    """

    zip_path = os.path.join(
        tempfile.gettempdir(),
        "national_store_info_20260331.zip"
    )

    # 이미 정상적으로 다운로드된 파일이 있다면 재사용
    if os.path.isfile(zip_path) and zipfile.is_zipfile(zip_path):
        return zip_path

    if os.path.exists(zip_path):
        os.remove(zip_path)

    with requests.get(
        DATA_URL,
        stream=True,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=(30, 300)
    ) as response:

        response.raise_for_status()

        with open(zip_path, "wb") as output:
            for chunk in response.iter_content(
                chunk_size=1024 * 1024
            ):
                if chunk:
                    output.write(chunk)

    # HTML 오류 페이지 등이 ZIP 대신 내려왔는지 확인
    if not zipfile.is_zipfile(zip_path):
        if os.path.exists(zip_path):
            os.remove(zip_path)

        raise ValueError(
            "다운로드한 파일이 정상적인 ZIP 파일이 아닙니다. "
            "공식 다운로드 주소가 변경되었는지 확인해 주세요."
        )

    return zip_path


# ==========================================
# 4. 지역별 CSV 파일 읽기
# ==========================================
@st.cache_data(
    ttl=86400,
    max_entries=4,
    show_spinner=False
)
def load_region_data(region_suffix, zip_path):
    """
    ZIP 내부에서 해당 지역의 CSV만 찾아 읽습니다.
    필요한 컬럼만 읽어 메모리 사용량을 줄입니다.
    """

    with zipfile.ZipFile(zip_path, "r") as archive:

        csv_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".csv")
        ]

        # 예: ..._서울_202603.csv
        pattern = re.compile(
            rf"_{re.escape(region_suffix)}_\d{{6}}\.csv$",
            re.IGNORECASE
        )

        matches = [
            name for name in csv_files
            if pattern.search(os.path.basename(name))
        ]

        # 파일명 규칙이 바뀐 경우를 위한 보조 검색
        if not matches:
            matches = [
                name for name in csv_files
                if f"_{region_suffix}_" in os.path.basename(name)
            ]

        if not matches:
            raise FileNotFoundError(
                f"ZIP 안에서 {region_suffix} 지역의 CSV를 찾지 못했습니다. "
                "공식 데이터의 파일명 형식이 변경되었을 수 있습니다."
            )

        # 여러 버전이 포함되어 있으면 파일명 기준으로 최신 날짜 선택
        def get_file_date(filename):
            match = re.search(
                r"_(\d{6})\.csv$",
                os.path.basename(filename)
            )
            return match.group(1) if match else "000000"

        target_file = sorted(matches, key=get_file_date)[-1]

        # 우선 컬럼명만 읽기
        with archive.open(target_file) as csv_file:
            header = pd.read_csv(
                csv_file,
                encoding="utf-8-sig",
                nrows=0
            )

        original_columns = list(header.columns)

        # 컬럼명 앞뒤 공백을 고려해 원본 컬럼명을 찾음
        normalized_to_original = {
            str(col).strip(): col
            for col in original_columns
        }

        # 원본 컬럼명 후보
        aliases = {
            "상가업소번호": ["상가업소번호"],
            "상호명": ["상호명"],
            "시도명": ["시도명"],
            "시군구명": ["시군구명"],
            "행정동명": ["행정동명", "행정동"],
            "법정동명": ["법정동명"],
            "상권업종대분류명": [
                "상권업종대분류명",
                "업종대분류명"
            ],
            "상권업종중분류명": [
                "상권업종중분류명",
                "업종중분류명"
            ],
            "상권업종소분류명": [
                "상권업종소분류명",
                "상권업종명",
                "업종명"
            ],
            "표준산업분류명": ["표준산업분류명"],
            "도로명주소": ["도로명주소"],
            "지번주소": ["지번주소"],
            "경도": ["경도"],
            "위도": ["위도"],
        }

        # 실제 파일에서 존재하는 컬럼만 선택
        source_columns = {}

        for standard_name, candidates in aliases.items():
            for candidate in candidates:
                if candidate in normalized_to_original:
                    source_columns[standard_name] = (
                        normalized_to_original[candidate]
                    )
                    break

        # 필수 지역 컬럼 확인
        if "시군구명" not in source_columns:
            raise ValueError(
                "CSV에서 시군구명 컬럼을 찾을 수 없습니다."
            )

        if (
            "행정동명" not in source_columns
            and "법정동명" not in source_columns
        ):
            raise ValueError(
                "CSV에서 행정동명 또는 법정동명 컬럼을 찾을 수 없습니다."
            )

        # 적어도 하나의 업종 분류가 있어야 분석 가능
        industry_columns = [
            "상권업종대분류명",
            "상권업종중분류명",
            "상권업종소분류명",
            "표준산업분류명",
        ]

        if not any(
            col in source_columns
            for col in industry_columns
        ):
            raise ValueError(
                "CSV에서 업종 분류 컬럼을 찾을 수 없습니다."
            )

        use_columns = list(set(source_columns.values()))

        # 필요한 컬럼만 불러오기
        with archive.open(target_file) as csv_file:
            raw = pd.read_csv(
                csv_file,
                encoding="utf-8-sig",
                usecols=use_columns,
                dtype=str,
                low_memory=False
            )

    raw.columns = raw.columns.astype(str).str.strip()

    # 분석에 사용할 표준 컬럼명으로 정리
    df = pd.DataFrame(index=raw.index)

    for standard_name, original_name in source_columns.items():
        normalized_name = str(original_name).strip()

        if normalized_name in raw.columns:
            df[standard_name] = raw[normalized_name]

    # 행정동명이 없으면 법정동명을 사용
    if "행정동명" not in df.columns:
        df["행정동명"] = df["법정동명"]

    elif "법정동명" in df.columns:
        df["행정동명"] = df["행정동명"].fillna(
            df["법정동명"]
        )

    # 문자열 공백 정리
    for col in df.columns:
        df[col] = df[col].astype("string").str.strip()

    # 지역 정보가 없는 행 제거
    df = df.dropna(
        subset=["시군구명", "행정동명"]
    )

    df = df[
        (df["시군구명"] != "")
        & (df["행정동명"] != "")
    ].copy()

    if df.empty:
        raise ValueError(
            "선택한 지역의 분석 가능한 데이터가 없습니다."
        )

    # 주소와 업종 분류의 빈 값 정리
    for col in [
        "상권업종대분류명",
        "상권업종중분류명",
        "상권업종소분류명",
        "표준산업분류명",
    ]:
        if col in df.columns:
            df[col] = df[col].replace("", pd.NA)

    # 소분류가 없는 행은 표준산업분류명으로 보완
    if (
        "상권업종소분류명" in df.columns
        and "표준산업분류명" in df.columns
    ):
        df["상권업종소분류명"] = (
            df["상권업종소분류명"]
            .fillna(df["표준산업분류명"])
        )

    return df


# ==========================================
# 5. 지역 선택
# ==========================================
st.divider()
st.subheader("📍 분석할 지역 선택")

# 시도 선택값을 기준으로 해당 지역 CSV를 읽음
current_sido = st.session_state.get(
    "selected_sido",
    REGION_NAMES[0]
)

if current_sido not in REGION_NAMES:
    current_sido = REGION_NAMES[0]

try:
    with st.spinner(
        f"{current_sido} 상가 데이터를 불러오는 중입니다..."
    ):
        zip_path = download_zip_to_disk()

        df = load_region_data(
            REGIONS[current_sido],
            zip_path
        )

except Exception as error:
    st.error("공식 상가 데이터를 불러오지 못했습니다.")
    st.write(
        "인터넷 연결, 공식 다운로드 주소 또는 ZIP 내부 파일명을 "
        "확인해야 합니다."
    )
    st.code(str(error))
    st.markdown(
        f"[공식 데이터 다운로드 페이지 열기]({DATA_PAGE_URL})"
    )
    st.stop()


# 세 개의 선택 메뉴를 같은 행에 배치
col1, col2, col3 = st.columns(3)

with col1:
    selected_sido = st.selectbox(
        "1. 시도",
        REGION_NAMES,
        index=REGION_NAMES.index(current_sido),
        key="selected_sido"
    )

# 현재 시도 파일만 사용하므로 별도의 시도 필터는 필요하지 않음
sigungu_list = sorted(
    df["시군구명"].dropna().unique().tolist()
)

if not sigungu_list:
    st.error("선택한 시도에서 시군구를 찾을 수 없습니다.")
    st.stop()

with col2:
    selected_sigungu = st.selectbox(
        "2. 시군구",
        sigungu_list,
        key="selected_sigungu"
    )

sigungu_df = df[
    df["시군구명"] == selected_sigungu
].copy()

dong_list = sorted(
    sigungu_df["행정동명"].dropna().unique().tolist()
)

if not dong_list:
    st.error("선택한 시군구에서 동 정보를 찾을 수 없습니다.")
    st.stop()

with col3:
    selected_dong = st.selectbox(
        "3. 동",
        dong_list,
        key="selected_dong"
    )


# ==========================================
# 6. 선택 지역 데이터
# ==========================================
area_df = sigungu_df[
    sigungu_df["행정동명"] == selected_dong
].copy()

if area_df.empty:
    st.warning("선택한 지역에 분석할 데이터가 없습니다.")
    st.stop()

st.write(
    f"**선택 지역:** {selected_sido} "
    f"{selected_sigungu} {selected_dong}"
)

st.caption(
    "아래 업소 수는 선택한 행정동의 상가정보 파일에서 "
    "집계한 점포 레코드 수입니다."
)


# ==========================================
# 7. 업종 분류 기준
# ==========================================
industry_levels = {
    "대분류": "상권업종대분류명",
    "중분류": "상권업종중분류명",
    "소분류": "상권업종소분류명",
    "표준산업분류": "표준산업분류명",
}

available_levels = []

for label, column in industry_levels.items():
    if (
        column in area_df.columns
        and area_df[column].notna().any()
    ):
        available_levels.append(label)

if not available_levels:
    st.error("선택 지역의 업종 분류 데이터가 없습니다.")
    st.stop()

st.divider()
st.subheader("📊 업종 분포 분석")

selected_level = st.selectbox(
    "업종 집계 기준",
    available_levels,
    index=available_levels.index(
        "소분류" if "소분류" in available_levels
        else available_levels[0]
    )
)

industry_column = industry_levels[selected_level]

area_df[industry_column] = (
    area_df[industry_column]
    .fillna("미분류")
    .replace("", "미분류")
)


# ==========================================
# 8. 핵심 지표
# ==========================================
industry_df = (
    area_df.groupby(industry_column, dropna=False)
    .size()
    .reset_index(name="업소 수")
    .rename(columns={industry_column: "업종"})
    .sort_values("업소 수", ascending=False)
    .reset_index(drop=True)
)

total_stores = len(area_df)
industry_count = len(industry_df)

top_industry = str(industry_df.iloc[0]["업종"])
top_count = int(industry_df.iloc[0]["업소 수"])

top_share = (
    top_count / total_stores * 100
    if total_stores > 0 else 0
)

m1, m2, m3 = st.columns(3)

m1.metric(
    "총 업소 수",
    f"{total_stores:,}개"
)

m2.metric(
    f"업종 수 ({selected_level})",
    f"{industry_count:,}개"
)

m3.metric(
    "업소 수 1위 업종",
    top_industry
)

st.write(
    f"**1위 업종:** {top_industry} · "
    f"**업소 수:** {top_count:,}개 · "
    f"**지역 내 비중:** {top_share:.1f}%"
)


# ==========================================
# 9. 업종별 막대그래프
# ==========================================
st.divider()
st.subheader("📈 업종별 업소 수 비교")

max_industries = st.slider(
    "표시할 상위 업종 수",
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
    y="업종",
    orientation="h",
    text="업소 수",
    title=(
        f"{selected_sido} {selected_sigungu} "
        f"{selected_dong} 업종별 업소 수"
    ),
    labels={
        "업소 수": "업소 수(개)",
        "업종": "업종"
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

st.plotly_chart(
    fig,
    use_container_width=True
)


# ==========================================
# 10. 창업 의사결정 참고
# ==========================================
st.divider()
st.subheader("💡 창업 의사결정 참고")

st.write(
    f"이 지역에서 업소 수가 가장 많은 "
    f"{selected_level} 업종은 **{top_industry}**입니다. "
    f"집계된 업소 수는 **{top_count:,}개**입니다."
)

if top_share >= 30:
    st.info(
        "1위 업종의 지역 내 비중이 비교적 높습니다. "
        "해당 업종을 창업 후보로 고려할 때는 경쟁 점포의 "
        "위치와 고객층을 추가로 조사해 보세요."
    )
else:
    st.info(
        "선택 지역의 업종 분포를 바탕으로 창업 아이템을 "
        "비교해 보세요. 업소 수만으로 수요나 수익성을 "
        "판단할 수는 없습니다."
    )

st.warning(
    "주의: 이 데이터는 개별 상가의 목록입니다. "
    "매출액, 순이익, 고객 수 또는 창업 성공 가능성을 "
    "직접 나타내지는 않습니다."
)


# ==========================================
# 11. 업종별 결과와 다운로드
# ==========================================
st.divider()
st.subheader("📋 업종별 분석 결과")

st.dataframe(
    industry_df,
    use_container_width=True,
    hide_index=True
)

download_data = industry_df.to_csv(
    index=False,
    encoding="utf-8-sig"
).encode("utf-8-sig")

st.download_button(
    label="📥 업종별 분석 결과 CSV 다운로드",
    data=download_data,
    file_name=(
        f"{selected_sido}_{selected_sigungu}_"
        f"{selected_dong}_상권분석.csv"
    ),
    mime="text/csv"
)


# ==========================================
# 12. 선택 지역의 상가 목록 미리보기
# ==========================================
st.divider()
st.subheader("🏬 선택 지역의 상가 목록")

display_columns = [
    "상호명",
    "상권업종대분류명",
    "상권업종중분류명",
    "상권업종소분류명",
    "표준산업분류명",
    "도로명주소",
    "지번주소",
]

display_columns = [
    col for col in display_columns
    if col in area_df.columns
]

with st.expander("상가 목록 미리보기 (최대 500개)"):
    st.dataframe(
        area_df[display_columns].head(500),
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        f"선택 지역의 전체 업소 수는 {len(area_df):,}개입니다. "
        "위 표는 처음 500개만 미리 보여 줍니다."
    )


# ==========================================
# 13. 데이터 출처
# ==========================================
st.divider()
st.subheader("📚 데이터 출처")

st.markdown(
    """
    - **제공기관:** 소상공인시장진흥공단
    - **데이터명:** 소상공인시장진흥공단 상가(상권)정보
    - **공식 다운로드 페이지:**  
      https://www.data.go.kr/data/15083033/fileData.do
    - **주요 항목:** 상가업소번호, 상호명, 업종 분류,
      시도명, 시군구명, 행정동명, 주소, 경도, 위도
    - **활용 목적:** 지역별 상가 수 및 업종 분포 분석
    """
)
