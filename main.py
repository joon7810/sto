    text="업소 수",
    title=f"{selected_sido} {selected_sigungu} {selected_dong} 업종별 업소 수",
    labels={"업소 수": "업소 수(개)", "업종": "업종"},
)
fig.update_traces(
    texttemplate="%{text:,}",
    textposition="outside",
    cliponaxis=False,
)
fig.update_layout(
    height=max(420, len(chart_df) * 35),
    margin=dict(l=20, r=60, t=60, b=20),
    xaxis_title="업소 수(개)",
    yaxis_title="업종",
)
st.plotly_chart(fig, use_container_width=True)


# ==========================================
# 11. 창업 의사결정 참고
# ==========================================
st.divider()
st.subheader("💡 창업 의사결정 참고")
st.write(
    f"이 지역에서 업소 수가 가장 많은 {selected_level} 업종은 "
    f"**{top_industry}**입니다. 집계된 업소 수는 **{top_count:,}개**입니다."
)

if top_share >= 30:
    st.info(
        "1위 업종의 지역 내 비중이 비교적 높습니다. "
        "해당 업종을 창업 후보로 고려할 때는 경쟁 점포의 "
        "위치와 고객층을 추가로 조사해 보세요."
    )
else:
    st.info(
        "선택 지역의 업종 분포를 바탕으로 창업 아이템을 비교해 보세요. "
        "업소 수만으로 수요나 수익성을 판단할 수는 없습니다."
    )

st.warning(
    "주의: 이 데이터는 개별 상가의 목록입니다. 매출액, 순이익, 고객 수 "
    "또는 창업 성공 가능성을 직접 나타내지는 않습니다."
)


# ==========================================
# 12. 업종별 결과와 다운로드
# ==========================================
st.divider()
st.subheader("📋 업종별 분석 결과")
st.dataframe(
    industry_df,
    use_container_width=True,
    hide_index=True,
)

download_data = industry_df.to_csv(
    index=False,
    encoding="utf-8-sig",
).encode("utf-8-sig")

st.download_button(
    label="📥 업종별 분석 결과 CSV 다운로드",
    data=download_data,
    file_name=f"{selected_sido}_{selected_sigungu}_{selected_dong}_상권분석.csv",
    mime="text/csv",
)


# ==========================================
# 13. 선택 지역의 상가 목록 미리보기
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
display_columns = [col for col in display_columns if col in area_df.columns]

with st.expander("상가 목록 미리보기 (최대 500개)"):
    st.dataframe(
        area_df[display_columns].head(500),
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        f"선택 지역의 전체 업소 수는 {len(area_df):,}개입니다. "
        "위 표는 처음 500개만 미리 보여 줍니다."
    )


# ==========================================
# 14. 데이터 출처
# ==========================================
st.divider()
st.subheader("📚 데이터 출처")
st.markdown(
    """
- **제공기관:** 소상공인시장진흥공단
- **데이터명:** 소상공인시장진흥공단 상가(상권)정보
- **공식 다운로드 페이지:** https://www.data.go.kr/data/15083033/fileData.do
- **주요 항목:** 상가업소번호, 상호명, 업종 분류, 시도명, 시군구명, 행정동명, 주소, 경도, 위도
- **활용 목적:** 지역별 상가 수 및 업종 분포 분석
    """
)
