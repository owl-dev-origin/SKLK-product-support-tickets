import datetime
import random
import json
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

S3_BUCKET = "shakalaka-maintenance"
S3_TICKET_PREFIX = "support-tickets/tickets/"

def get_s3_client():
    return boto3.client(
        "s3",
        region_name="ap-northeast-2",
        aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
    )

def load_all_tickets():
    s3 = get_s3_client()
    tickets = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_TICKET_PREFIX):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".json"):
                response = s3.get_object(Bucket=S3_BUCKET, Key=obj["Key"])
                ticket = json.loads(response["Body"].read())
                tickets.append(ticket)
    if not tickets:
        return pd.DataFrame(columns=["ID", "작성자", "서비스 대상", "요청 유형", "내용", "상태", "우선순위", "제출일", "이미지 URL"])
    df = pd.DataFrame(tickets)
    df = df.sort_values("ID", ascending=False).reset_index(drop=True)
    return df

def save_ticket(ticket):
    s3 = get_s3_client()
    key = f"{S3_TICKET_PREFIX}{ticket['ID']}.json"
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=json.dumps(ticket, ensure_ascii=False, default=str), ContentType="application/json")

def get_next_ticket_id():
    s3 = get_s3_client()
    max_num = 1000
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=S3_TICKET_PREFIX):
        for obj in page.get("Contents", []):
            name = obj["Key"].split("/")[-1].replace(".json", "")
            if name.startswith("TICKET-"):
                num = int(name.split("-")[1])
                max_num = max(max_num, num)
    return f"TICKET-{max_num + 1}"

if "df" not in st.session_state:
    st.session_state.df = load_all_tickets()

def upload_image_to_s3(file, ticket_id, index):
    s3 = get_s3_client()
    ext = file.name.rsplit(".", 1)[-1] if "." in file.name else "png"
    key = f"support-tickets/images/{ticket_id}_{index}.{ext}"
    try:
        s3.upload_fileobj(file, S3_BUCKET, key)
        url = f"https://{S3_BUCKET}.s3.ap-northeast-2.amazonaws.com/{key}"
        return url
    except NoCredentialsError:
        st.error("AWS 자격증명을 확인해주세요.")
        return None
    
# 사용법 안내
with st.expander("📖 사용법 안내"):
    st.markdown(
        """
        **티켓 작성 방법**  
        0. **작성자** 입력: 본인 이름을 입력합니다.  
        1. **서비스 대상** 선택: 요청이 해당하는 서비스를 선택합니다.  
            - `sklk-사용자` : Shakalaka 앱 (사용자 화면, shakalaka.kr)
            - `sklk-관리자` : Shakalaka 앱 (관리자/운영 화면, admin.shakalaka.kr)
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
    author = st.text_input("작성자")
    service = st.selectbox("서비스 대상", ["sklk-사용자", "sklk-관리자", "mgmt", "내부운영도구"])
    request_type = st.selectbox("요청 유형", ["버그", "기능 개선", "신규 개발", "기타"])
    priority = st.selectbox("우선순위", ["높음", "중간", "낮음"])
    issue = st.text_area("내용 (증상, 재현 방법, 기대 동작 등을 상세히 작성해주세요~)")
    uploaded_files = st.file_uploader("이미지 첨부 (선택, 다중 첨부 가능)", type=["png", "jpg", "jpeg", "gif", "webp"], accept_multiple_files=True)
    submit_date = st.date_input("제출일", value=datetime.date.today())
    submitted = st.form_submit_button("제출")

if submitted:
    if not author.strip():
        st.warning("작성자를 입력해주세요.")
    elif not issue.strip():
        st.warning("내용을 입력해주세요.")
    else:
        new_id = get_next_ticket_id()
        today = submit_date.strftime("%Y-%m-%d")

        image_urls = []
        for idx, file in enumerate(uploaded_files):
            url = upload_image_to_s3(file, new_id, idx + 1)
            if url:
                image_urls.append(url)

        new_ticket = {
            "ID": new_id,
            "작성자": author,
            "서비스 대상": service,
            "요청 유형": request_type,
            "내용": issue,
            "상태": "접수",
            "우선순위": priority,
            "제출일": today,
            "이미지 URL": ", ".join(image_urls),
        }

        save_ticket(new_ticket)

        st.success("티켓이 등록되었습니다!")
        st.dataframe(pd.DataFrame([new_ticket]), use_container_width=True, hide_index=True)
        st.session_state.df = load_all_tickets()

# 기존 티켓 목록
st.header("티켓 목록")

col_a, col_b = st.columns([1, 5])
with col_a:
    if st.button("🔄 새로고침"):
        st.session_state.df = load_all_tickets()
        st.rerun()
with col_b:
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
                options=["접수", "처리 중", "보류", "완료"],
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
        disabled=["ID", "작성자", "서비스 대상", "요청 유형", "내용", "제출일", "이미지 URL"],
    )

    if not edited_df.equals(st.session_state.df):
        changed_rows = edited_df[
            (edited_df["상태"] != st.session_state.df["상태"])
            | (edited_df["우선순위"] != st.session_state.df["우선순위"])
        ]
        for _, row in changed_rows.iterrows():
            save_ticket(row.to_dict())
        st.session_state.df = edited_df
        st.rerun()

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