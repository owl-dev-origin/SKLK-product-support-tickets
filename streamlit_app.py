import datetime
import random
import boto3
from botocore.exceptions import NoCredentialsError

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st
    
st.set_page_config(page_title="개발 요청 티켓", page_icon="🎫", layout='wide')
st.title("🎫 개발 요청 티켓")
st.write(
    """
    아울소싸이어티 구성원들이 제품에 대한 버그 신고, 기능 개선, 신규 개발 요청 등을 티켓으로 등록하는 도구입니다.  
    아래 양식을 작성하여 티켓을 제출하면 기존 티켓 목록에 추가됩니다.
    """
)

if "df" not in st.session_state:
    df = pd.DataFrame(columns=["ID", "서비스 대상", "요청 유형", "내용", "상태", "우선순위", "제출일"])
    st.session_state.df = df

def upload_image_to_s3(file, ticket_id):
    s3 = boto3.client(
        "s3",
        region_name="ap-northeast-2",
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
    )
    bucket = "shakalaka-maintenance"
    key = f"support-tickets/{ticket_id}/{file.name}"
    try:
        s3.upload_fileobj(file, bucket, key)
        url = f"https://{bucket}.s3.ap-northeast-2.amazonaws.com/{key}"
        return url
    except NoCredentialsError:
        st.error("AWS 자격증명을 확인해주세요.")
        return None
    
# 사용법 안내
with st.expander("📖 사용법 안내"):
    st.markdown(
        """
        **티켓 작성 방법**
        1. **서비스 대상** 선택: 요청이 해당하는 서비스를 선택합니다.
            - `sklk` : Shakalaka 앱의 사용자 및 관리자 페이지 (shakalaka.kr / admin.shakalaka.kr)
            - `mgmt` : Shakalaka management (mgmt.shakalaka.kr)
            - `내부운영도구` : 대시보드 등 앱을 제외한 별도 기능을 하는 내부 도구
        2. **요청 유형** 선택: 요청의 성격을 선택합니다.
            - `버그` : 오작동, 오류, 예상과 다른 동작
            - `기능 개선` : 기존 기능의 수정 또는 개선
            - `신규 개발` : 새로운 기능 또는 도구 개발
            - `기타` : 위 유형에 해당하지 않는 요청
        3. **우선순위** 선택 후 내용을 상세히 작성하고 제출합니다. 우선순위는 개발팀(원선)에서 프로젝트 상황에 따라 변경할 수 있습니다.

        **티켓 관리 방법**
        - 아래 티켓 목록에서 셀을 더블클릭하면 **상태**와 **우선순위**를 직접 수정할 수 있습니다.
        - 열 헤더를 클릭하면 정렬이 가능합니다.
        """
    )

# 티켓 추가 섹션
st.header("티켓 등록")

with st.form("add_ticket_form"):
    service = st.selectbox("서비스 대상", ["sklk", "mgmt", "내부운영도구"])
    request_type = st.selectbox("요청 유형", ["버그", "기능 개선", "신규 개발", "기타"])
    priority = st.selectbox("우선순위", ["높음", "중간", "낮음"])
    issue = st.text_area("내용 (증상, 재현 방법, 기대 동작 등을 상세히 작성해주세요)")
    uploaded_file = st.file_uploader("이미지 첨부 (선택)", type=["png", "jpg", "jpeg", "gif", "webp"])
    submit_date = st.date_input("제출일", value=datetime.date.today())
    submitted = st.form_submit_button("제출")

if submitted:
    if not issue.strip():
        st.warning("내용을 입력해주세요.")
    else:
        if len(st.session_state.df) == 0:
            new_id = "TICKET-1001"
        else:
            recent_number = int(max(st.session_state.df.ID).split("-")[1])
            new_id = f"TICKET-{recent_number + 1}"

        today = submit_date.strftime("%Y-%m-%d")

        image_url = None
        if uploaded_file is not None:
            image_url = upload_image_to_s3(uploaded_file, new_id)

        df_new = pd.DataFrame([{
            "ID": new_id,
            "서비스 대상": service,
            "요청 유형": request_type,
            "내용": issue,
            "상태": "접수",
            "우선순위": priority,
            "제출일": today,
            "이미지 URL": image_url if image_url else "",
        }])

        st.success("티켓이 등록되었습니다!")
        st.dataframe(df_new, use_container_width=True, hide_index=True)
        st.session_state.df = pd.concat([df_new, st.session_state.df], axis=0)

# 기존 티켓 목록
st.header("티켓 목록")
st.write(f"전체 티켓 수: `{len(st.session_state.df)}`")

st.info("셀을 더블클릭하면 상태와 우선순위를 수정할 수 있습니다. 열 헤더를 클릭하면 정렬됩니다.", icon="✍️")

if len(st.session_state.df) == 0:
    st.caption("등록된 티켓이 없습니다. 위 양식으로 첫 티켓을 등록해보세요.")
else:
    edited_df = st.data_editor(
        st.session_state.df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "상태": st.column_config.SelectboxColumn(
                "상태",
                help="티켓 처리 상태",
                options=["접수", "처리 중", "완료"],
                required=True,
            ),
            "우선순위": st.column_config.SelectboxColumn(
                "우선순위",
                help="처리 우선순위",
                options=["높음", "중간", "낮음"],
                required=True,
            ),
            "이미지 URL": st.column_config.LinkColumn(
                "이미지",
                help="첨부 이미지 링크",
                display_text="보기",
            ),
        },
        disabled=["ID", "서비스 대상", "요청 유형", "내용", "제출일", "이미지 URL"],
    )

    # 통계 섹션
    st.header("통계")

    col1, col2, col3 = st.columns(3)
    num_open = len(edited_df[edited_df["상태"] == "접수"])
    num_in_progress = len(edited_df[edited_df["상태"] == "처리 중"])
    num_closed = len(edited_df[edited_df["상태"] == "완료"])
    col1.metric(label="접수", value=num_open)
    col2.metric(label="처리 중", value=num_in_progress)
    col3.metric(label="완료", value=num_closed)

    st.write("")
    st.write("##### 서비스 대상별 요청 유형")
    chart1 = (
        alt.Chart(edited_df)
        .mark_bar()
        .encode(
            x=alt.X("서비스 대상:N", title="서비스 대상"),
            y=alt.Y("count():Q", title="티켓 수"),
            xOffset="요청 유형:N",
            color="요청 유형:N",
        )
        .configure_legend(orient="bottom", titleFontSize=13, labelFontSize=13)
    )
    st.altair_chart(chart1, use_container_width=True, theme="streamlit")

    st.write("##### 우선순위 분포")
    chart2 = (
        alt.Chart(edited_df)
        .mark_arc()
        .encode(theta="count():Q", color="우선순위:N")
        .properties(height=300)
        .configure_legend(orient="bottom", titleFontSize=13, labelFontSize=13)
    )
    st.altair_chart(chart2, use_container_width=True, theme="streamlit")