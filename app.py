
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import date

# ---------------------------------
# 1. 기본 설정
# ---------------------------------

st.set_page_config(
    page_title="WaterCheck",
    page_icon="💧",
    layout="wide"
)

API_URL = "http://apis.data.go.kr/B500001/rwis/waterQuality/list"

st.title("💧 WaterCheck")
st.subheader("지역별 생활용수 수질 분석 시스템")

st.write(
    "공공데이터 API를 활용하여 정수장 수질 측정값을 조회하고 "
    "시간에 따른 변화를 분석합니다."
)

st.divider()

# ---------------------------------
# 2. 조회 조건 입력
# ---------------------------------

st.header("1. 수질 데이터 조회")

with st.form("search_form"):

    col1, col2 = st.columns(2)

    with col1:
        facility_no = st.text_input(
            "시설관리번호",
            value="4824012333"
        )

        business_code = st.text_input(
            "사업장코드",
            value="333"
        )

        water_type = st.text_input(
            "생활공업구분",
            value="1"
        )

        start_date = st.date_input(
            "조회 시작일자",
            value=date.today()
        )

        start_hour = st.selectbox(
            "조회 시작시간",
            [f"{i:02d}" for i in range(24)],
            index=17
        )

    with col2:
        end_date = st.date_input(
            "조회 종료일자",
            value=date.today()
        )

        end_hour = st.selectbox(
            "조회 종료시간",
            [f"{i:02d}" for i in range(25)],
            index=18
        )

        rows = st.selectbox(
            "한 번에 조회할 데이터 수",
            [10, 20, 50, 100],
            index=2
        )

        page = st.number_input(
            "페이지 번호",
            min_value=1,
            value=1,
            step=1
        )

    submitted = st.form_submit_button(
        "수질 데이터 조회",
        use_container_width=True
    )

# ---------------------------------
# 3. API 데이터 요청
# ---------------------------------

if submitted:

    if start_date > end_date:
        st.error("조회 종료일은 시작일보다 빠를 수 없습니다.")

    elif start_date == end_date and start_hour >= end_hour:
        st.error("같은 날짜라면 종료시간은 시작시간보다 늦어야 합니다.")

    else:

        # Streamlit Secrets에서 인증키 가져오기
        try:
            service_key = st.secrets["SERVICE_KEY"]

        except Exception:
            st.error(
                "API 인증키를 찾을 수 없습니다. "
                "Streamlit Secrets에 SERVICE_KEY를 등록해 주세요."
            )
            st.stop()

        params = {
            "serviceKey": service_key,
            "stDt": start_date.strftime("%Y-%m-%d"),
            "stTm": start_hour,
            "edDt": end_date.strftime("%Y-%m-%d"),
            "edTm": end_hour,
            "numOfRows": rows,
            "pageNo": page,
            "_type": "json"
        }

        # 선택 입력값이 있을 때만 추가
        if facility_no.strip():
            params["fcltyMngNo"] = facility_no.strip()

        if business_code.strip():
            params["sujCode"] = business_code.strip()

        if water_type.strip():
            params["lilndDiv"] = water_type.strip()

        try:
            with st.spinner("수질 데이터를 불러오는 중입니다..."):

                response = requests.get(
                    API_URL,
                    params=params,
                    timeout=60
                )

                response.raise_for_status()

                result = response.json()

            header = result.get("response", {}).get("header", {})
            body = result.get("response", {}).get("body", {})

            if header.get("resultCode") != "00":
                st.error(
                    "API 오류: " +
                    str(header.get("resultMsg"))
                )
                st.stop()

            items = body.get("items", "")

            if not items:
                st.warning(
                    "해당 조건에 맞는 수질 데이터가 없습니다. "
                    "조회 날짜와 시간을 변경해 보세요."
                )
                st.stop()

            records = items.get("item", [])

            if isinstance(records, dict):
                records = [records]

            if not records:
                st.warning("조회된 측정 데이터가 없습니다.")
                st.stop()

            # ---------------------------------
            # 4. 데이터 정리
            # ---------------------------------

            df = pd.DataFrame(records)

            df["측정시각"] = pd.to_datetime(
                df["occrrncDt"].astype(str),
                format="%Y%m%d%H",
                errors="coerce"
            )

            numeric_columns = [
                "phVal",
                "clVal",
                "tbVal"
            ]

            for column in numeric_columns:
                df[column] = pd.to_numeric(
                    df[column],
                    errors="coerce"
                )

            df = df.dropna(subset=["측정시각"])

            df = df.sort_values("측정시각")

            df = df.rename(columns={
                "fcltyMngNm": "정수장",
                "fcltyAddr": "주소",
                "phVal": "pH",
                "clVal": "잔류염소",
                "tbVal": "탁도",
                "clUnit": "잔류염소 단위",
                "tbUnit": "탁도 단위"
            })

            # ---------------------------------
            # 5. 조회 결과 출력
            # ---------------------------------

            st.divider()
            st.header("2. 수질 측정 결과")

            first = df.iloc[0]

            st.success(
                f"조회 성공: {len(df)}건의 수질 데이터를 가져왔습니다."
            )

            col1, col2 = st.columns(2)

            with col1:
                st.metric("정수장", first["정수장"])

            with col2:
                st.metric("조회 데이터", f"{len(df)}건")

            # 수질 측정값 표
            display_columns = [
                "측정시각",
                "정수장",
                "pH",
                "잔류염소",
                "탁도"
            ]

            if "주소" in df.columns:
                display_columns.insert(2, "주소")

            st.dataframe(
                df[display_columns],
                use_container_width=True,
                hide_index=True
            )

            # ---------------------------------
            # 6. 통계 분석
            # ---------------------------------

            st.header("3. 수질 데이터 통계")

            metric_columns = [
                ("pH", "pH"),
                ("잔류염소", "잔류염소 (mg/L)"),
                ("탁도", "탁도 (NTU)")
            ]

            cols = st.columns(3)

            for col, (column, label) in zip(cols, metric_columns):

                values = df[column].dropna()

                with col:
                    st.subheader(label)

                    if not values.empty:
                        st.metric(
                            "평균",
                            f"{values.mean():.4f}"
                        )

                        st.caption(
                            f"최솟값: {values.min():.4f} / "
                            f"최댓값: {values.max():.4f}"
                        )
                    else:
                        st.write("측정값 없음")

            # ---------------------------------
            # 7. 수질 변화 그래프
            # ---------------------------------

            st.header("4. 시간별 수질 변화")

            selected = st.selectbox(
                "그래프로 확인할 수질 항목",
                ["pH", "잔류염소", "탁도"]
            )

            unit = {
                "pH": "pH",
                "잔류염소": "mg/L",
                "탁도": "NTU"
            }

            graph_df = df.dropna(subset=[selected])

            if not graph_df.empty:

                fig = px.line(
                    graph_df,
                    x="측정시각",
                    y=selected,
                    markers=True,
                    title=f"{selected} 시간별 변화",
                    labels={
                        selected: f"{selected} ({unit[selected]})",
                        "측정시각": "측정 시각"
                    }
                )

                st.plotly_chart(
                    fig,
                    use_container_width=True
                )

            else:
                st.info("선택한 항목의 측정값이 없습니다.")

            # ---------------------------------
            # 8. 화학적 원리 설명
            # ---------------------------------

            st.header("5. 수질 항목의 화학적 원리")

            explanations = {
                "pH": (
                    "pH는 수소 이온 농도를 나타내는 척도이다. "
                    "수소 이온 농도가 높을수록 pH는 낮아지고, "
                    "낮을수록 pH는 높아진다."
                ),

                "잔류염소": (
                    "염소는 물속에서 차아염소산(HOCl)과 "
                    "차아염소산 이온(OCl⁻) 등의 형태로 존재한다. "
                    "이러한 물질은 미생물을 불활성화하는 소독 작용을 한다."
                ),

                "탁도": (
                    "탁도는 물속에 존재하는 부유 입자에 의해 "
                    "빛이 산란되는 정도와 관련된 지표이다. "
                    "일반적으로 탁도가 높을수록 물이 흐려 보인다."
                )
            }

            st.info(explanations[selected])

            st.caption(
                "※ 이 자료는 정수장 측정값이며, 가정 수도꼭지의 "
                "수질을 직접 측정한 결과는 아닙니다. "
                "일부 항목만으로 전체 음용 안전성을 판단할 수 없습니다."
            )

            # ---------------------------------
            # 9. CSV 다운로드
            # ---------------------------------

            csv = df.to_csv(
                index=False,
                encoding="utf-8-sig"
            )

            st.download_button(
                "측정 데이터 CSV 다운로드",
                data=csv,
                file_name="watercheck_data.csv",
                mime="text/csv"
            )

        except requests.exceptions.Timeout:
            st.error(
                "API 서버 응답 시간이 초과되었습니다. "
                "잠시 후 다시 시도해 주세요."
            )

        except requests.exceptions.RequestException as e:
            st.error(f"API 연결 오류: {e}")

        except Exception as e:
            st.error(f"데이터 처리 중 오류가 발생했습니다: {e}")
