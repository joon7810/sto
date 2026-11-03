import os\
import re\
import tempfile\
import zipfile\
\
import pandas as pd\
import plotly.express as px\
import requests\
import streamlit as st\
\
\
\# ==========================================\
\# 1. 기본 설정\
\# ==========================================\
st.set_page_config(\
&#x20;   page_title="전국 상권 분석",\
&#x20;   page_icon="🏪",\
&#x20;   layout="wide"\
)\
\
st.title("🏪 전국 상권 분석 및 창업 의사결정")\
st.write(\
&#x20;   "전국의 지역별 상가와 업종 분포를 분석해 "\
&#x20;   "창업 아이템을 탐색하는 프로그램입니다."\
)\
\
st.caption(\
&#x20;   "데이터 제공기관: 소상공인시장진흥공단 | "\
&#x20;   "자료 기준일: 2026년 3월 31일"\
)\
\
\
\# ==========================================\
\# 2. 전국 데이터 다운로드 주소\
\# ==========================================\
\# 공식 공공데이터포털에 등록된 ZIP 파일의 직접 다운로드 주소\
DATA_URL = (\
&#x20;   "https\://www\.data.go.kr/cmm/cmm/fileDownload.do"\
&#x20;   "?atchFileId=FILE_000000003632420"\
&#x20;   "&fileDetailSn=1"\
&#x20;   "&insertDataPrcus=N"\
)\
\
DATA_PAGE_URL = "https\://www\.data.go.kr/data/15083033/fileData.do"\
\
\
\# 전국 17개 시·도와 ZIP 내부 파일명의 지역 코드\
REGIONS = {\
&#x20;   "강원특별자치도": "강원",\
&#x20;   "경기도": "경기",\
&#x20;   "경상남도": "경남",\
&#x20;   "경상북도": "경북",\
&#x20;   "광주광역시": "광주",\
&#x20;   "대구광역시": "대구",\
&#x20;   "대전광역시": "대전",\
&#x20;   "부산광역시": "부산",\
&#x20;   "서울특별시": "서울",\
&#x20;   "세종특별자치시": "세종",\
&#x20;   "울산광역시": "울산",\
&#x20;   "인천광역시": "인천",\
&#x20;   "전라남도": "전남",\
&#x20;   "전북특별자치도": "전북",\
&#x20;   "제주특별자치도": "제주",\
&#x20;   "충청남도": "충남",\
&#x20;   "충청북도": "충북",\
}\
\
REGION_NAMES = list(REGIONS.keys())\
\
\
\# ==========================================\
\# 3. ZIP 파일 자동 다운로드\
\# ==========================================\
@st.cache_resource(show_spinner=False)\
def download_zip_to_disk():\
&#x20;   """\
&#x20;   공식 데이터 ZIP 파일을 임시 디스크에 저장합니다.\
&#x20;   전체 파일을 메모리에 한꺼번에 올리지 않습니다.\
&#x20;   """\
\
&#x20;   zip_path = os.path.join(\
&#x20;       tempfile.gettempdir(),\
&#x20;       "national_store_info_20260331.zip"\
&#x20;   )\
\
&#x20;   \# 이미 정상적으로 다운로드된 파일이 있다면 재사용\
&#x20;   if os.path.isfile(zip_path) and zipfile.is_zipfile(zip_path):\
&#x20;       return zip_path\
\
&#x20;   if os.path.exists(zip_path):\
&#x20;       os.remove(zip_path)\
\
&#x20;   with requests.get(\
&#x20;       DATA_URL,\
&#x20;       stream=True,\
&#x20;       headers={"User-Agent": "Mozilla/5.0"},\
&#x20;       timeout=(30, 300)\
&#x20;   ) as response:\
\
&#x20;       response.raise_for_status()\
\
&#x20;       with open(zip_path, "wb") as output:\
&#x20;           for chunk in response.iter_content(\
&#x20;               chunk_size=1024 \* 1024\
&#x20;           ):\
&#x20;               if chunk:\
&#x20;                   output.write(chunk)\
\
&#x20;   \# HTML 오류 페이지 등이 ZIP 대신 내려왔는지 확인\
&#x20;   if not zipfile.is_zipfile(zip_path):\
&#x20;       if os.path.exists(zip_path):\
&#x20;           os.remove(zip_path)\
\
&#x20;       raise ValueError(\
&#x20;           "다운로드한 파일이 정상적인 ZIP 파일이 아닙니다. "\
&#x20;           "공식 다운로드 주소가 변경되었는지 확인해 주세요."\
&#x20;       )\
\
&#x20;   return zip_path\
\
\
\# ==========================================\
\# 4. 지역별 CSV 파일 읽기\
\# ==========================================\
@st.cache_data(\
&#x20;   ttl=86400,\
&#x20;   max_entries=4,\
&#x20;   show_spinner=False\
)\
def load_region_data(region_suffix, zip_path):\
&#x20;   """\
&#x20;   ZIP 내부에서 해당 지역의 CSV만 찾아 읽습니다.\
&#x20;   필요한 컬럼만 읽어 메모리 사용량을 줄입니다.\
&#x20;   """\
\
&#x20;   with zipfile.ZipFile(zip_path, "r") as archive:\
\
&#x20;       csv_files = [\
&#x20;           name for name in archive.namelist()\
&#x20;           if name.lower().endswith(".csv")\
&#x20;       ]\
\
&#x20;       \# 예: ...\_서울_202603.csv\
&#x20;       pattern = re.compile(\
&#x20;           rf"\_{re.escape(region_suffix)}\_\d{{6}}\\.csv$",\
&#x20;           re.IGNORECASE\
&#x20;       )\
\
&#x20;       matches = [\
&#x20;           name for name in csv_files\
&#x20;           if pattern.search(os.path.basename(name))\
&#x20;       ]\
\
&#x20;       \# 파일명 규칙이 바뀐 경우를 위한 보조 검색\
&#x20;       if not matches:\
&#x20;           matches = [\
&#x20;               name for name in csv_files\
&#x20;               if f"\_{region_suffix}\_" in os.path.basename(name)\
&#x20;           ]\
\
&#x20;       if not matches:\
&#x20;           raise FileNotFoundError(\
&#x20;               f"ZIP 안에서 {region_suffix} 지역의 CSV를 찾지 못했습니다. "\
&#x20;               "공식 데이터의 파일명 형식이 변경되었을 수 있습니다."\
&#x20;           )\
\
&#x20;       \# 여러 버전이 포함되어 있으면 파일명 기준으로 최신 날짜 선택\
&#x20;       def get_file_date(filename):\
&#x20;           match = re.search(\
&#x20;               r"\_(\d{6})\\.csv$",\
&#x20;               os.path.basename(filename)\
&#x20;           )\
&#x20;           return match.group(1) if match else "000000"\
\
&#x20;       target_file = sorted(matches, key=get_file_date)[-1]\
\
&#x20;       \# 우선 컬럼명만 읽기\
&#x20;       with archive.open(target_file) as csv_file:\
&#x20;           header = pd.read_csv(\
&#x20;               csv_file,\
&#x20;               encoding="utf-8-sig",\
&#x20;               nrows=0\
&#x20;           )\
\
&#x20;       original_columns = list(header.columns)\
\
&#x20;       \# 컬럼명 앞뒤 공백을 고려해 원본 컬럼명을 찾음\
&#x20;       normalized_to_original = {\
&#x20;           str(col).strip(): col\
&#x20;           for col in original_columns\
&#x20;       }\
\
&#x20;       \# 원본 컬럼명 후보\
&#x20;       aliases = {\
&#x20;           "상가업소번호": ["상가업소번호"],\
&#x20;           "상호명": ["상호명"],\
&#x20;           "시도명": ["시도명"],\
&#x20;           "시군구명": ["시군구명"],\
&#x20;           "행정동명": ["행정동명", "행정동"],\
&#x20;           "법정동명": ["법정동명"],\
&#x20;           "상권업종대분류명": [\
&#x20;               "상권업종대분류명",\
&#x20;               "업종대분류명"\
&#x20;           ],\
&#x20;           "상권업종중분류명": [\
&#x20;               "상권업종중분류명",\
&#x20;               "업종중분류명"\
&#x20;           ],\
&#x20;           "상권업종소분류명": [\
&#x20;               "상권업종소분류명",\
&#x20;               "상권업종명",\
&#x20;               "업종명"\
&#x20;           ],\
&#x20;           "표준산업분류명": ["표준산업분류명"],\
&#x20;           "도로명주소": ["도로명주소"],\
&#x20;           "지번주소": ["지번주소"],\
&#x20;           "경도": ["경도"],\
&#x20;           "위도": ["위도"],\
&#x20;       }\
\
&#x20;       \# 실제 파일에서 존재하는 컬럼만 선택\
&#x20;       source_columns = {}\
\
&#x20;       for standard_name, candidates in aliases.items():\
&#x20;           for candidate in candidates:\
&#x20;               if candidate in normalized_to_original:\
&#x20;                   source_columns[standard_name] = (\
&#x20;                       normalized_to_original[candidate]\
&#x20;                   )\
&#x20;                   break\
\
&#x20;       \# 필수 지역 컬럼 확인\
&#x20;       if "시군구명" not in source_columns:\
&#x20;           raise ValueError(\
&#x20;               "CSV에서 시군구명 컬럼을 찾을 수 없습니다."\
&#x20;           )\
\
&#x20;       if (\
&#x20;           "행정동명" not in source_columns\
&#x20;           and "법정동명" not in source_columns\
&#x20;       ):\
&#x20;           raise ValueError(\
&#x20;               "CSV에서 행정동명 또는 법정동명 컬럼을 찾을 수 없습니다."\
&#x20;           )\
\
&#x20;       \# 적어도 하나의 업종 분류가 있어야 분석 가능\
&#x20;       industry_columns = [\
&#x20;           "상권업종대분류명",\
&#x20;           "상권업종중분류명",\
&#x20;           "상권업종소분류명",\
&#x20;           "표준산업분류명",\
&#x20;       ]\
\
&#x20;       if not any(\
&#x20;           col in source_columns\
&#x20;           for col in industry_columns\
&#x20;       ):\
&#x20;           raise ValueError(\
&#x20;               "CSV에서 업종 분류 컬럼을 찾을 수 없습니다."\
&#x20;           )\
\
&#x20;       use_columns = list(set(source_columns.values()))\
\
&#x20;       \# 필요한 컬럼만 불러오기\
&#x20;       with archive.open(target_file) as csv_file:\
&#x20;           raw = pd.read_csv(\
&#x20;               csv_file,\
&#x20;               encoding="utf-8-sig",\
&#x20;               usecols=use_columns,\
&#x20;               dtype=str,\
&#x20;               low_memory=False\
&#x20;           )\
\
&#x20;   raw\.columns = raw\.columns.astype(str).str.strip()\
\
&#x20;   \# 분석에 사용할 표준 컬럼명으로 정리\
&#x20;   df = pd.DataFrame(index=raw\.index)\
\
&#x20;   for standard_name, original_name in source_columns.items():\
&#x20;       normalized_name = str(original_name).strip()\
\
&#x20;       if normalized_name in raw\.columns:\
&#x20;           df[standard_name] = raw[normalized_name]\
\
&#x20;   \# 행정동명이 없으면 법정동명을 사용\
&#x20;   if "행정동명" not in df.columns:\
&#x20;       df["행정동명"] = df["법정동명"]\
\
&#x20;   elif "법정동명" in df.columns:\
&#x20;       df["행정동명"] = df["행정동명"].fillna(\
&#x20;           df["법정동명"]\
&#x20;       )\
\
&#x20;   \# 문자열 공백 정리\
&#x20;   for col in df.columns:\
&#x20;       df[col] = df[col].astype("string").str.strip()\
\
&#x20;   \# 지역 정보가 없는 행 제거\
&#x20;   df = df.dropna(\
&#x20;       subset=["시군구명", "행정동명"]\
&#x20;   )\
\
&#x20;   df = df[\
&#x20;       (df["시군구명"] != "")\
&#x20;       & (df["행정동명"] != "")\
&#x20;   ].copy()\
\
&#x20;   if df.empty:\
&#x20;       raise ValueError(\
&#x20;           "선택한 지역의 분석 가능한 데이터가 없습니다."\
&#x20;       )\
\
&#x20;   \# 주소와 업종 분류의 빈 값 정리\
&#x20;   for col in [\
&#x20;       "상권업종대분류명",\
&#x20;       "상권업종중분류명",\
&#x20;       "상권업종소분류명",\
&#x20;       "표준산업분류명",\
&#x20;   ]:\
&#x20;       if col in df.columns:\
&#x20;           df[col] = df[col].replace("", pd.NA)\
\
&#x20;   \# 소분류가 없는 행은 표준산업분류명으로 보완\
&#x20;   if (\
&#x20;       "상권업종소분류명" in df.columns\
&#x20;       and "표준산업분류명" in df.columns\
&#x20;   ):\
&#x20;       df["상권업종소분류명"] = (\
&#x20;           df["상권업종소분류명"]\
&#x20;           .fillna(df["표준산업분류명"])\
&#x20;       )\
\
&#x20;   return df\
\
\
\# ==========================================\
\# 5. 지역 선택\
\# ==========================================\
st.divider()\
st.subheader("📍 분석할 지역 선택")\
\
\# 시도 선택값을 기준으로 해당 지역 CSV를 읽음\
current_sido = st.session_state.get(\
&#x20;   "selected_sido",\
&#x20;   REGION_NAMES[0]\
)\
\
if current_sido not in REGION_NAMES:\
&#x20;   current_sido = REGION_NAMES[0]\
\
try:\
&#x20;   with st.spinner(\
&#x20;       f"{current_sido} 상가 데이터를 불러오는 중입니다..."\
&#x20;   ):\
&#x20;       zip_path = download_zip_to_disk()\
\
&#x20;       df = load_region_data(\
&#x20;           REGIONS[current_sido],\
&#x20;           zip_path\
&#x20;       )\
\
except Exception as error:\
&#x20;   st.error("공식 상가 데이터를 불러오지 못했습니다.")\
&#x20;   st.write(\
&#x20;       "인터넷 연결, 공식 다운로드 주소 또는 ZIP 내부 파일명을 "\
&#x20;       "확인해야 합니다."\
&#x20;   )\
&#x20;   st.code(str(error))\
&#x20;   st.markdown(\
&#x20;       f"[공식 데이터 다운로드 페이지 열기]\({DATA_PAGE_URL})"\
&#x20;   )\
&#x20;   st.stop()\
\
\
\# 세 개의 선택 메뉴를 같은 행에 배치\
col1, col2, col3 = st.columns(3)\
\
with col1:\
&#x20;   selected_sido = st.selectbox(\
&#x20;       "1. 시도",\
&#x20;       REGION_NAMES,\
&#x20;       index=REGION_NAMES.index(current_sido),\
&#x20;       key="selected_sido"\
&#x20;   )\
\
\# 현재 시도 파일만 사용하므로 별도의 시도 필터는 필요하지 않음\
sigungu_list = sorted(\
&#x20;   df["시군구명"].dropna().unique().tolist()\
)\
\
if not sigungu_list:\
&#x20;   st.error("선택한 시도에서 시군구를 찾을 수 없습니다.")\
&#x20;   st.stop()\
\
with col2:\
&#x20;   selected_sigungu = st.selectbox(\
&#x20;       "2. 시군구",\
&#x20;       sigungu_list,\
&#x20;       key="selected_sigungu"\
&#x20;   )\
\
sigungu_df = df[\
&#x20;   df["시군구명"] == selected_sigungu\
].copy()\
\
dong_list = sorted(\
&#x20;   sigungu_df["행정동명"].dropna().unique().tolist()\
)\
\
if not dong_list:\
&#x20;   st.error("선택한 시군구에서 동 정보를 찾을 수 없습니다.")\
&#x20;   st.stop()\
\
with col3:\
&#x20;   selected_dong = st.selectbox(\
&#x20;       "3. 동",\
&#x20;       dong_list,\
&#x20;       key="selected_dong"\
&#x20;   )\
\
\
\# ==========================================\
\# 6. 선택 지역 데이터\
\# ==========================================\
area_df = sigungu_df[\
&#x20;   sigungu_df["행정동명"] == selected_dong\
].copy()\
\
if area_df.empty:\
&#x20;   st.warning("선택한 지역에 분석할 데이터가 없습니다.")\
&#x20;   st.stop()\
\
st.write(\
&#x20;   f"\*\*선택 지역:\*\* {selected_sido} "\
&#x20;   f"{selected_sigungu} {selected_dong}"\
)\
\
st.caption(\
&#x20;   "아래 업소 수는 선택한 행정동의 상가정보 파일에서 "\
&#x20;   "집계한 점포 레코드 수입니다."\
)\
\
\
\# ==========================================\
\# 7. 업종 분류 기준\
\# ==========================================\
industry_levels = {\
&#x20;   "대분류": "상권업종대분류명",\
&#x20;   "중분류": "상권업종중분류명",\
&#x20;   "소분류": "상권업종소분류명",\
&#x20;   "표준산업분류": "표준산업분류명",\
}\
\
available_levels = []\
\
for label, column in industry_levels.items():\
&#x20;   if (\
&#x20;       column in area_df.columns\
&#x20;       and area_df[column].notna().any()\
&#x20;   ):\
&#x20;       available_levels.append(label)\
\
if not available_levels:\
&#x20;   st.error("선택 지역의 업종 분류 데이터가 없습니다.")\
&#x20;   st.stop()\
\
st.divider()\
st.subheader("📊 업종 분포 분석")\
\
selected_level = st.selectbox(\
&#x20;   "업종 집계 기준",\
&#x20;   available_levels,\
&#x20;   index=available_levels.index(\
&#x20;       "소분류" if "소분류" in available_levels\
&#x20;       else available_levels[0]\
&#x20;   )\
)\
\
industry_column = industry_levels[selected_level]\
\
area_df[industry_column] = (\
&#x20;   area_df[industry_column]\
&#x20;   .fillna("미분류")\
&#x20;   .replace("", "미분류")\
)\
\
\
\# ==========================================\
\# 8. 핵심 지표\
\# ==========================================\
industry_df = (\
&#x20;   area_df.groupby(industry_column, dropna=False)\
&#x20;   .size()\
&#x20;   .reset_index(name="업소 수")\
&#x20;   .rename(columns={industry_column: "업종"})\
&#x20;   .sort_values("업소 수", ascending=False)\
&#x20;   .reset_index(drop=True)\
)\
\
total_stores = len(area_df)\
industry_count = len(industry_df)\
\
top_industry = str(industry_df.iloc[0]["업종"])\
top_count = int(industry_df.iloc[0]["업소 수"])\
\
top_share = (\
&#x20;   top_count / total_stores \* 100\
&#x20;   if total_stores > 0 else 0\
)\
\
m1, m2, m3 = st.columns(3)\
\
m1.metric(\
&#x20;   "총 업소 수",\
&#x20;   f"{total_stores:,}개"\
)\
\
m2.metric(\
&#x20;   f"업종 수 ({selected_level})",\
&#x20;   f"{industry_count:,}개"\
)\
\
m3.metric(\
&#x20;   "업소 수 1위 업종",\
&#x20;   top_industry\
)\
\
st.write(\
&#x20;   f"\*\*1위 업종:\*\* {top_industry} · "\
&#x20;   f"\*\*업소 수:\*\* {top_count:,}개 · "\
&#x20;   f"\*\*지역 내 비중:\*\* {top_share:.1f}%"\
)\
\
\
\# ==========================================\
\# 9. 업종별 막대그래프\
\# ==========================================\
st.divider()\
st.subheader("📈 업종별 업소 수 비교")\
\
max_industries = st.slider(\
&#x20;   "표시할 상위 업종 수",\
&#x20;   min_value=5,\
&#x20;   max_value=30,\
&#x20;   value=10,\
&#x20;   step=5\
)\
\
chart_df = industry_df.head(max_industries).copy()\
chart_df = chart_df.sort_values("업소 수", ascending=True)\
\
fig = px.bar(\
&#x20;   chart_df,\
&#x20;   x="업소 수",\
&#x20;   y="업종",\
&#x20;   orientation="h",\
&#x20;   text="업소 수",\
&#x20;   title=(\
&#x20;       f"{selected_sido} {selected_sigungu} "\
&#x20;       f"{selected_dong} 업종별 업소 수"\
&#x20;   ),\
&#x20;   labels={\
&#x20;       "업소 수": "업소 수(개)",\
&#x20;       "업종": "업종"\
&#x20;   }\
)\
\
fig.update_traces(\
&#x20;   texttemplate="%{text:,}",\
&#x20;   textposition="outside",\
&#x20;   cliponaxis=False\
)\
\
fig.update_layout(\
&#x20;   height=max(420, len(chart_df) \* 35),\
&#x20;   margin=dict(l=20, r=60, t=60, b=20),\
&#x20;   xaxis_title="업소 수(개)",\
&#x20;   yaxis_title="업종"\
)\
\
st.plotly_chart(\
&#x20;   fig,\
&#x20;   use_container_width=True\
)\
\
\
\# ==========================================\
\# 10. 창업 의사결정 참고\
\# ==========================================\
st.divider()\
st.subheader("💡 창업 의사결정 참고")\
\
st.write(\
&#x20;   f"이 지역에서 업소 수가 가장 많은 "\
&#x20;   f"{selected_level} 업종은 \*\*{top_industry}\*\*입니다. "\
&#x20;   f"집계된 업소 수는 \*\*{top_count:,}개\*\*입니다."\
)\
\
if top_share >= 30:\
&#x20;   st.info(\
&#x20;       "1위 업종의 지역 내 비중이 비교적 높습니다. "\
&#x20;       "해당 업종을 창업 후보로 고려할 때는 경쟁 점포의 "\
&#x20;       "위치와 고객층을 추가로 조사해 보세요."\
&#x20;   )\
else:\
&#x20;   st.info(\
&#x20;       "선택 지역의 업종 분포를 바탕으로 창업 아이템을 "\
&#x20;       "비교해 보세요. 업소 수만으로 수요나 수익성을 "\
&#x20;       "판단할 수는 없습니다."\
&#x20;   )\
\
st.warning(\
&#x20;   "주의: 이 데이터는 개별 상가의 목록입니다. "\
&#x20;   "매출액, 순이익, 고객 수 또는 창업 성공 가능성을 "\
&#x20;   "직접 나타내지는 않습니다."\
)\
\
\
\# ==========================================\
\# 11. 업종별 결과와 다운로드\
\# ==========================================\
st.divider()\
st.subheader("📋 업종별 분석 결과")\
\
st.dataframe(\
&#x20;   industry_df,\
&#x20;   use_container_width=True,\
&#x20;   hide_index=True\
)\
\
download_data = industry_df.to_csv(\
&#x20;   index=False,\
&#x20;   encoding="utf-8-sig"\
).encode("utf-8-sig")\
\
st.download_button(\
&#x20;   label="📥 업종별 분석 결과 CSV 다운로드",\
&#x20;   data=download_data,\
&#x20;   file_name=(\
&#x20;       f"{selected_sido}\_{selected_sigungu}\_"\
&#x20;       f"{selected_dong}\_상권분석.csv"\
&#x20;   ),\
&#x20;   mime="text/csv"\
)\
\
\
\# ==========================================\
\# 12. 선택 지역의 상가 목록 미리보기\
\# ==========================================\
st.divider()\
st.subheader("🏬 선택 지역의 상가 목록")\
\
display_columns = [\
&#x20;   "상호명",\
&#x20;   "상권업종대분류명",\
&#x20;   "상권업종중분류명",\
&#x20;   "상권업종소분류명",\
&#x20;   "표준산업분류명",\
&#x20;   "도로명주소",\
&#x20;   "지번주소",\
]\
\
display_columns = [\
&#x20;   col for col in display_columns\
&#x20;   if col in area_df.columns\
]\
\
with st.expander("상가 목록 미리보기 (최대 500개)"):\
&#x20;   st.dataframe(\
&#x20;       area_df[display_columns].head(500),\
&#x20;       use_container_width=True,\
&#x20;       hide_index=True\
&#x20;   )\
\
&#x20;   st.caption(\
&#x20;       f"선택 지역의 전체 업소 수는 {len(area_df):,}개입니다. "\
&#x20;       "위 표는 처음 500개만 미리 보여 줍니다."\
&#x20;   )\
\
\
\# ==========================================\
\# 13. 데이터 출처\
\# ==========================================\
st.divider()\
st.subheader("📚 데이터 출처")\
\
st.markdown(\
&#x20;   """\
&#x20;   \- \*\*제공기관:\*\* 소상공인시장진흥공단\
&#x20;   \- \*\*데이터명:\*\* 소상공인시장진흥공단 상가(상권)정보\
&#x20;   \- \*\*공식 다운로드 페이지:\*\*  \
&#x20;     https\://www\.data.go.kr/data/15083033/fileData.do\
&#x20;   \- \*\*주요 항목:\*\* 상가업소번호, 상호명, 업종 분류,\
&#x20;     시도명, 시군구명, 행정동명, 주소, 경도, 위도\
&#x20;   \- \*\*활용 목적:\*\* 지역별 상가 수 및 업종 분포 분석\
&#x20;   """\
)\
