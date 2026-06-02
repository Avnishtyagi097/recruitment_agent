import streamlit as st
import json
import re
import random
import hashlib
import smtplib
import pandas as pd
from datetime import datetime, timedelta
from collections import Counter
from io import BytesIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI Recruitment Screening Agent",
    page_icon="\U0001f916",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# SESSION STATE INITIALISATION
# ─────────────────────────────────────────────
defaults = {
    "candidates": {},
    "pipeline_logs": [],
    "current_candidate_id": None,
    "current_stage": "CV Upload & ATS",
    "assessment_started": False,
    "assessment_answers": {},
    "assessment_submitted": False,
    "assessment_questions": [],
    "assessment_result": None,
    "assessment_start_time": None,
    "recruiter_name": "TalentEdge Recruitment Team",
    "recruiter_email": "recruit@talentedge.ai",
    # SMTP / Email automation
    "smtp_server": "smtp.gmail.com",
    "smtp_port": 587,
    "sender_email": "",
    "sender_password": "",
    "smtp_configured": False,
    "auto_email_enabled": True,
    "email_log": [],
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────
# EMAIL FUNCTIONS
# ─────────────────────────────────────────────

def send_email(to_email, subject, body_text):
    """Send an email via SMTP. Returns (success: bool, message: str)."""
    if not st.session_state.smtp_configured:
        return False, "SMTP not configured. Email queued for manual review."
    try:
        msg = MIMEMultipart("alternative")
        msg["From"] = formataddr((st.session_state.recruiter_name, st.session_state.sender_email))
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body_text, "plain", "utf-8"))

        with smtplib.SMTP(st.session_state.smtp_server, st.session_state.smtp_port, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(st.session_state.sender_email, st.session_state.sender_password)
            server.sendmail(st.session_state.sender_email, to_email, msg.as_string())
        return True, "Email sent successfully."
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed. Check email/password or enable App Passwords."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Email error: {str(e)}"


def log_email(to_email, subject, email_type, status, detail):
    """Log every email action."""
    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "to": to_email,
        "subject": subject,
        "type": email_type,
        "status": status,
        "detail": detail,
    }
    st.session_state.email_log.append(entry)
    return entry


def send_and_log(to_email, subject, body, email_type):
    """Send an email and log the result. Returns (success, message)."""
    if st.session_state.auto_email_enabled and st.session_state.smtp_configured:
        ok, msg = send_email(to_email, subject, body)
        status = "SENT" if ok else "FAILED"
    else:
        ok = False
        msg = "Auto-email disabled or SMTP not configured. Email content generated for manual sending."
        status = "QUEUED"
    log_email(to_email, subject, email_type, status, msg)
    return ok, msg, status


def auto_pipeline_action(candidate_data, action_type):
    """
    Automate the full pipeline action after a decision.
    Returns a list of action summaries.
    """
    actions = []
    c_name = candidate_data["name"]
    c_email = candidate_data.get("email", "")
    role = candidate_data["role"]
    recruiter_name = st.session_state.recruiter_name
    recruiter_email = st.session_state.recruiter_email
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if action_type == "ats_fail":
        # 1. Send rejection to candidate
        subj = f"Update on Your Application for {role}"
        body = generate_rejection_email(c_name, role, "ATS", recruiter_name)
        if c_email:
            ok, msg, status = send_and_log(c_email, subj, body, "ATS Rejection → Candidate")
            actions.append({"action": "Rejection email to candidate", "to": c_email, "status": status, "detail": msg})
            candidate_data["emails_sent"].append({"type": "ATS Rejection", "content": body, "timestamp": now_str, "send_status": status})
        # 2. Notify recruiter
        r_subj = f"[ATS FAIL] Candidate Rejected: {c_name} — {role}"
        r_body = f"Candidate: {c_name}\nEmail: {c_email}\nRole: {role}\nATS Score: {candidate_data['ats_result']['ats_score']}\nDecision: FAIL\nReason: {candidate_data['ats_result']['reasoning_summary']}\n\nRejection email has been sent to the candidate."
        if recruiter_email:
            ok2, msg2, status2 = send_and_log(recruiter_email, r_subj, r_body, "ATS Rejection → Recruiter Notification")
            actions.append({"action": "Recruiter notification (ATS FAIL)", "to": recruiter_email, "status": status2, "detail": msg2})

    elif action_type == "ats_pass":
        # 1. Send assessment invitation to candidate
        deadline = (datetime.now() + timedelta(days=2)).strftime("%B %d, %Y at 11:59 PM UTC")
        subj = f"Next Step: Assessment for {role}"
        body = generate_assessment_email(c_name, role, deadline, recruiter_name)
        if c_email:
            ok, msg, status = send_and_log(c_email, subj, body, "Assessment Invitation → Candidate")
            actions.append({"action": "Assessment invitation to candidate", "to": c_email, "status": status, "detail": msg})
            candidate_data["emails_sent"].append({"type": "Assessment Invitation", "content": body, "timestamp": now_str, "send_status": status})
        # 2. Notify recruiter
        r_subj = f"[ATS PASS] New Candidate Shortlisted: {c_name} — {role}"
        r_body = f"Candidate: {c_name}\nEmail: {c_email}\nRole: {role}\nATS Score: {candidate_data['ats_result']['ats_score']}\nDecision: PASS\n\nAssessment invitation has been sent to the candidate.\nDeadline: {deadline}"
        if recruiter_email:
            ok2, msg2, status2 = send_and_log(recruiter_email, r_subj, r_body, "ATS Pass → Recruiter Notification")
            actions.append({"action": "Recruiter notification (ATS PASS)", "to": recruiter_email, "status": status2, "detail": msg2})

    elif action_type == "assessment_fail":
        # 1. Send rejection to candidate
        subj = f"Update on Your Application for {role}"
        body = generate_rejection_email(c_name, role, "Assessment", recruiter_name)
        if c_email:
            ok, msg, status = send_and_log(c_email, subj, body, "Assessment Rejection → Candidate")
            actions.append({"action": "Rejection email to candidate", "to": c_email, "status": status, "detail": msg})
            candidate_data["emails_sent"].append({"type": "Assessment Rejection", "content": body, "timestamp": now_str, "send_status": status})
        # 2. Notify recruiter
        assess = candidate_data.get("assessment_result", {})
        r_subj = f"[ASSESSMENT FAIL] Candidate Rejected: {c_name} — {role}"
        r_body = f"Candidate: {c_name}\nEmail: {c_email}\nRole: {role}\nAssessment Score: {assess.get('score_percent', 0)}%\nDecision: FAIL\n\nRejection email has been sent to the candidate."
        if recruiter_email:
            ok2, msg2, status2 = send_and_log(recruiter_email, r_subj, r_body, "Assessment Rejection → Recruiter Notification")
            actions.append({"action": "Recruiter notification (Assessment FAIL)", "to": recruiter_email, "status": status2, "detail": msg2})

    elif action_type == "assessment_pass":
        # 1. Generate interview slots and send invite to candidate
        availability = get_panel_availability(role)
        slots = availability["slots"]
        subj = f"Interview Scheduling for {role}"
        body = generate_interview_email(c_name, role, slots, recruiter_name)
        if c_email:
            ok, msg, status = send_and_log(c_email, subj, body, "Interview Invitation → Candidate")
            actions.append({"action": "Interview invitation to candidate", "to": c_email, "status": status, "detail": msg})
            candidate_data["emails_sent"].append({"type": "Interview Invitation", "content": body, "timestamp": now_str, "send_status": status})
        candidate_data["interview_scheduled"] = True
        candidate_data["interview_slots"] = slots
        candidate_data["interview_panel"] = availability["panel"]
        # 2. Notify recruiter
        assess = candidate_data.get("assessment_result", {})
        r_subj = f"[INTERVIEW READY] Candidate Cleared: {c_name} — {role}"
        panel_names = ", ".join([p["name"] for p in availability["panel"]])
        slot_summary = "\n".join([f"  - {s['date']} at {s['time']}" for s in slots[:6]])
        r_body = f"Candidate: {c_name}\nEmail: {c_email}\nRole: {role}\nATS Score: {candidate_data['ats_result']['ats_score']}\nAssessment Score: {assess.get('score_percent', 0)}%\n\nInterview invitation has been sent to the candidate.\n\nPanel: {panel_names}\nAvailable Slots:\n{slot_summary}"
        if recruiter_email:
            ok2, msg2, status2 = send_and_log(recruiter_email, r_subj, r_body, "Interview Ready → Recruiter Notification")
            actions.append({"action": "Recruiter notification (Interview Ready)", "to": recruiter_email, "status": status2, "detail": msg2})

    return actions


# ─────────────────────────────────────────────
# JOB DESCRIPTION TEMPLATES
# ─────────────────────────────────────────────
JD_TEMPLATES = {
    "Data Engineer": """
Role: Data Engineer
Experience Required: 3-6 years

Responsibilities:
- Design, build, and maintain scalable data pipelines using ETL/ELT frameworks.
- Develop and optimize SQL queries and stored procedures for data transformation.
- Work with Apache Spark, PySpark, and Databricks for large-scale data processing.
- Design and maintain data warehouse schemas (star/snowflake) in cloud environments.
- Orchestrate workflows using Apache Airflow or similar tools.
- Implement data quality frameworks, monitoring, and governance best practices.
- Collaborate with analytics and ML teams to deliver clean, reliable datasets.
- Manage data on cloud platforms (AWS S3, Azure Data Lake, GCP BigQuery).

Required Skills:
- Python, SQL, Spark, PySpark, Databricks
- ETL/ELT design and implementation
- Data warehousing (Snowflake, Redshift, BigQuery)
- Apache Airflow, dbt
- Cloud platforms: AWS / Azure / GCP
- Data modeling (star schema, snowflake schema, data vault)
- Batch and streaming data processing (Kafka, Kinesis)
- Performance optimization and query tuning
- Data governance and cataloging (e.g., Apache Atlas, Collibra)
- CI/CD for data pipelines, version control (Git)

Preferred Certifications:
- Databricks Certified Data Engineer
- AWS Certified Data Analytics
- Google Professional Data Engineer
- Azure Data Engineer Associate

Education:
- Bachelor's or Master's in Computer Science, Data Science, Information Systems, or related field.
""",
    "Software Engineer": """
Role: Software Engineer
Experience Required: 2-5 years

Responsibilities:
- Design, develop, test, and maintain scalable software applications.
- Write clean, efficient, and well-documented code.
- Participate in code reviews and contribute to engineering best practices.
- Build and consume RESTful APIs and microservices.
- Work with relational and NoSQL databases.
- Deploy applications using CI/CD pipelines and container orchestration.
- Collaborate with product, design, and QA teams.

Required Skills:
- Python, Java, or JavaScript/TypeScript
- REST APIs, GraphQL
- Microservices architecture
- SQL, PostgreSQL, MongoDB
- Docker, Kubernetes
- CI/CD (Jenkins, GitHub Actions)
- Unit testing, TDD
- Git, Agile/Scrum
- Cloud platforms: AWS / Azure / GCP
- System design fundamentals

Preferred Certifications:
- AWS Certified Developer
- Azure Developer Associate
- Certified Kubernetes Application Developer (CKAD)

Education:
- Bachelor's or Master's in Computer Science, Software Engineering, or related field.
""",
    "Data Analyst": """
Role: Data Analyst
Experience Required: 1-4 years

Responsibilities:
- Analyze large datasets to identify trends, patterns, and insights.
- Create dashboards and reports using BI tools.
- Write complex SQL queries for data extraction and analysis.
- Collaborate with business stakeholders to define KPIs and metrics.
- Clean and validate data for accuracy and integrity.
- Present findings through data storytelling.

Required Skills:
- SQL, Excel (advanced)
- Python or R for data analysis
- Tableau, Power BI, Looker
- Statistical analysis and hypothesis testing
- Data cleaning and wrangling (Pandas, NumPy)
- Data visualization best practices
- Basic understanding of ETL processes
- Communication and presentation skills
- Git, Jupyter Notebooks

Preferred Certifications:
- Google Data Analytics Certificate
- Microsoft Certified: Data Analyst Associate
- Tableau Desktop Specialist

Education:
- Bachelor's in Statistics, Mathematics, Data Science, Economics, or related field.
""",
    "DevOps Engineer": """
Role: DevOps Engineer
Experience Required: 3-6 years

Responsibilities:
- Design and implement CI/CD pipelines for automated build, test, and deployment.
- Manage cloud infrastructure using Infrastructure as Code (Terraform, CloudFormation).
- Monitor system performance and ensure high availability.
- Containerize applications using Docker and orchestrate with Kubernetes.
- Implement security best practices across the pipeline.
- Manage configuration with Ansible, Chef, or Puppet.
- Troubleshoot production incidents and conduct root cause analysis.

Required Skills:
- Linux, Bash scripting, Python
- Docker, Kubernetes, Helm
- Terraform, CloudFormation, Ansible
- CI/CD: Jenkins, GitLab CI, GitHub Actions
- AWS / Azure / GCP cloud services
- Monitoring: Prometheus, Grafana, ELK stack, Datadog
- Networking basics (DNS, TCP/IP, load balancing)
- Security: IAM, secrets management, vulnerability scanning
- Git, GitOps practices
- Incident management and SRE principles

Preferred Certifications:
- AWS Certified DevOps Engineer
- Certified Kubernetes Administrator (CKA)
- HashiCorp Certified: Terraform Associate
- Azure DevOps Engineer Expert

Education:
- Bachelor's in Computer Science, Information Technology, or related field.
""",
}

# ─────────────────────────────────────────────
# QUESTION BANKS
# ─────────────────────────────────────────────
QUESTION_BANKS = {
"Data Engineer": [
  {"q":"What does ETL stand for?","options":["Extract, Transform, Load","Execute, Transfer, Log","Extract, Transfer, Load","Execute, Transform, Load"],"answer":0,"topic":"ETL","difficulty":"easy"},
  {"q":"Which SQL clause is used to filter groups of rows?","options":["WHERE","HAVING","GROUP BY","ORDER BY"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"In a star schema, fact tables are connected to:","options":["Other fact tables","Dimension tables","Staging tables","Log tables"],"answer":1,"topic":"Data Modeling","difficulty":"easy"},
  {"q":"Which Apache Spark component is used for structured data processing?","options":["Spark Streaming","MLlib","Spark SQL","GraphX"],"answer":2,"topic":"Spark","difficulty":"easy"},
  {"q":"What is the primary purpose of Apache Airflow?","options":["Data storage","Workflow orchestration","Real-time streaming","Machine learning"],"answer":1,"topic":"Orchestration","difficulty":"easy"},
  {"q":"Which Python library is most commonly used for data manipulation?","options":["NumPy","Matplotlib","Pandas","Scikit-learn"],"answer":2,"topic":"Python","difficulty":"easy"},
  {"q":"In data warehousing, what is a slowly changing dimension (SCD)?","options":["A dimension that never changes","A dimension that tracks changes over time","A dimension used for real-time data","A temporary staging dimension"],"answer":1,"topic":"Data Warehousing","difficulty":"medium"},
  {"q":"What is the difference between batch and stream processing?","options":["Batch is real-time; stream is periodic","Batch processes data in chunks; stream processes data continuously","They are the same","Batch is faster than streaming"],"answer":1,"topic":"Batch vs Streaming","difficulty":"easy"},
  {"q":"Which of the following is a columnar storage format?","options":["CSV","JSON","Parquet","XML"],"answer":2,"topic":"Data Warehousing","difficulty":"easy"},
  {"q":"What does the ACID property 'Isolation' guarantee?","options":["Data is saved permanently","Transactions don't interfere with each other","All operations succeed or none do","Data remains valid"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"In Spark, what is a DataFrame?","options":["A distributed collection of key-value pairs","A distributed collection of data organized into named columns","A Python dictionary","A type of RDD with no schema"],"answer":1,"topic":"Spark","difficulty":"easy"},
  {"q":"Which partitioning strategy splits data by date?","options":["Hash partitioning","Range partitioning","Round-robin partitioning","Random partitioning"],"answer":1,"topic":"Performance Optimization","difficulty":"medium"},
  {"q":"What is the purpose of a data catalog?","options":["Store raw data","Provide metadata management and data discovery","Run ETL jobs","Monitor dashboards"],"answer":1,"topic":"Governance","difficulty":"easy"},
  {"q":"Which AWS service is a serverless data warehouse?","options":["RDS","DynamoDB","Redshift Serverless","S3"],"answer":2,"topic":"Cloud","difficulty":"medium"},
  {"q":"What is schema-on-read?","options":["Schema is enforced when data is written","Schema is applied when data is read","Schema is never used","Schema is stored in a separate database"],"answer":1,"topic":"Data Modeling","difficulty":"medium"},
  {"q":"In Kafka, what is a topic?","options":["A consumer group","A category to which records are published","A type of broker","A serialization format"],"answer":1,"topic":"Batch vs Streaming","difficulty":"easy"},
  {"q":"What transformation does a window function perform in SQL?","options":["Filters rows before aggregation","Performs calculations across a set of rows related to the current row","Joins two tables","Creates a new table"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"Which tool is commonly used for data transformation in the modern data stack?","options":["Hadoop MapReduce","dbt (data build tool)","Apache Pig","Sqoop"],"answer":1,"topic":"ETL","difficulty":"medium"},
  {"q":"What is data lineage?","options":["The speed of data transfer","The tracking of data's origin and transformations","The size of a dataset","A data encryption method"],"answer":1,"topic":"Governance","difficulty":"easy"},
  {"q":"In Databricks, what is a Delta table?","options":["A temporary view","An ACID-compliant table format built on Parquet","A CSV file","A streaming-only table"],"answer":1,"topic":"Databricks","difficulty":"medium"},
  {"q":"Which join returns all rows from both tables, matching where possible?","options":["INNER JOIN","LEFT JOIN","FULL OUTER JOIN","CROSS JOIN"],"answer":2,"topic":"SQL","difficulty":"easy"},
  {"q":"What is the purpose of an idempotent pipeline?","options":["It runs only once","Re-running it produces the same result without side effects","It processes data faster","It requires no input"],"answer":1,"topic":"ETL","difficulty":"medium"},
  {"q":"Which Spark action triggers computation on an RDD?","options":["map()","filter()","collect()","flatMap()"],"answer":2,"topic":"Spark","difficulty":"medium"},
  {"q":"What is the CAP theorem?","options":["A data modeling technique","A theorem about consistency, availability, and partition tolerance","A caching strategy","A compression algorithm"],"answer":1,"topic":"Data Warehousing","difficulty":"medium"},
  {"q":"In Python, which library is used for connecting to databases using an ORM?","options":["requests","sqlalchemy","flask","beautifulsoup"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"What is a materialized view?","options":["A virtual table that runs a query each time","A stored result set of a query","A temporary table","An index on a table"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"Which Azure service is used for big data analytics?","options":["Azure Blob Storage","Azure Synapse Analytics","Azure Functions","Azure DevOps"],"answer":1,"topic":"Cloud","difficulty":"medium"},
  {"q":"What is data skew in distributed processing?","options":["Uniform data distribution","Uneven distribution of data across partitions","A type of data corruption","A sorting algorithm"],"answer":1,"topic":"Performance Optimization","difficulty":"medium"},
  {"q":"What is the role of a schema registry in streaming?","options":["Store data permanently","Manage and enforce schemas for messages","Route messages to topics","Monitor consumer lag"],"answer":1,"topic":"Batch vs Streaming","difficulty":"medium"},
  {"q":"Which orchestration pattern uses a DAG?","options":["Linear pipeline","Directed Acyclic Graph workflow","Circular workflow","Ad-hoc scheduling"],"answer":1,"topic":"Orchestration","difficulty":"easy"},
  {"q":"What is change data capture (CDC)?","options":["Capturing all data at once","Identifying and capturing changes made to data","A backup strategy","A data encryption method"],"answer":1,"topic":"ETL","difficulty":"medium"},
  {"q":"In Spark, what is the difference between narrow and wide transformations?","options":["Narrow requires shuffling; wide does not","Wide requires shuffling; narrow does not","They are identical","Narrow is slower"],"answer":1,"topic":"Spark","difficulty":"hard"},
  {"q":"What is a data vault modeling approach?","options":["A replacement for all data models","A methodology using hubs, links, and satellites","A type of star schema","A NoSQL design pattern"],"answer":1,"topic":"Data Modeling","difficulty":"hard"},
  {"q":"Which Python decorator is used for caching function results?","options":["@staticmethod","@lru_cache","@property","@classmethod"],"answer":1,"topic":"Python","difficulty":"medium"},
  {"q":"What is the purpose of data partitioning in a data lake?","options":["Encrypt data","Improve query performance by reducing data scanned","Compress files","Create backups"],"answer":1,"topic":"Performance Optimization","difficulty":"medium"},
],
"Software Engineer": [
  {"q":"What is the time complexity of binary search?","options":["O(n)","O(log n)","O(n log n)","O(1)"],"answer":1,"topic":"Algorithms","difficulty":"easy"},
  {"q":"Which HTTP method is idempotent?","options":["POST","PATCH","PUT","None of the above"],"answer":2,"topic":"REST APIs","difficulty":"easy"},
  {"q":"What is the SOLID principle 'S' for?","options":["Single Responsibility","Separation of Concerns","Singleton Pattern","Secure coding"],"answer":0,"topic":"Design Principles","difficulty":"easy"},
  {"q":"In a microservices architecture, what is an API Gateway?","options":["A database","A single entry point for API calls","A testing tool","A deployment server"],"answer":1,"topic":"Microservices","difficulty":"easy"},
  {"q":"Which data structure uses FIFO?","options":["Stack","Queue","Tree","Graph"],"answer":1,"topic":"Data Structures","difficulty":"easy"},
  {"q":"What does Docker containerization provide?","options":["Hardware virtualization","OS-level isolation for applications","Compiler optimization","Database management"],"answer":1,"topic":"Docker","difficulty":"easy"},
  {"q":"What is the purpose of a load balancer?","options":["Store data","Distribute traffic across servers","Compile code","Manage databases"],"answer":1,"topic":"System Design","difficulty":"easy"},
  {"q":"Which testing level verifies individual components?","options":["Integration testing","Unit testing","System testing","Acceptance testing"],"answer":1,"topic":"Testing","difficulty":"easy"},
  {"q":"What is a deadlock?","options":["A fast execution path","Two or more processes waiting for each other indefinitely","A type of exception","A memory leak"],"answer":1,"topic":"Concurrency","difficulty":"medium"},
  {"q":"In Git, what does 'rebase' do?","options":["Deletes a branch","Re-applies commits on top of another base","Merges two repos","Creates a tag"],"answer":1,"topic":"Git","difficulty":"medium"},
  {"q":"What is the CAP theorem relevant to?","options":["UI design","Distributed systems","Compiler design","Sorting algorithms"],"answer":1,"topic":"System Design","difficulty":"medium"},
  {"q":"Which design pattern ensures a class has only one instance?","options":["Factory","Observer","Singleton","Strategy"],"answer":2,"topic":"Design Patterns","difficulty":"easy"},
  {"q":"What is the purpose of an ORM?","options":["Optimize rendering","Map objects to database tables","Manage operating systems","Route network packets"],"answer":1,"topic":"Databases","difficulty":"easy"},
  {"q":"In REST, what status code indicates 'Created'?","options":["200","201","204","301"],"answer":1,"topic":"REST APIs","difficulty":"easy"},
  {"q":"What is CI/CD?","options":["Code Inspection/Code Deployment","Continuous Integration/Continuous Delivery","Central Index/Central Database","Compiled Instructions/Compiled Data"],"answer":1,"topic":"DevOps","difficulty":"easy"},
  {"q":"Which Kubernetes object manages stateless applications?","options":["StatefulSet","Deployment","DaemonSet","Job"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is a race condition?","options":["A performance benchmark","When output depends on uncontrolled timing of events","A networking protocol","A type of sort"],"answer":1,"topic":"Concurrency","difficulty":"medium"},
  {"q":"What is the difference between SQL and NoSQL databases?","options":["SQL is unstructured; NoSQL is structured","SQL uses fixed schemas; NoSQL is schema-flexible","They are the same","NoSQL cannot store data"],"answer":1,"topic":"Databases","difficulty":"easy"},
  {"q":"What does 'DRY' stand for in software engineering?","options":["Don't Repeat Yourself","Data Replication Yield","Dynamic Resource Yielding","Deploy Run Yell"],"answer":0,"topic":"Design Principles","difficulty":"easy"},
  {"q":"Which protocol does GraphQL use?","options":["FTP","HTTP","SMTP","SSH"],"answer":1,"topic":"REST APIs","difficulty":"easy"},
  {"q":"What is a hash table's average lookup time?","options":["O(n)","O(log n)","O(1)","O(n^2)"],"answer":2,"topic":"Data Structures","difficulty":"easy"},
  {"q":"What is blue-green deployment?","options":["A testing strategy","Running two identical production environments for zero-downtime releases","A color-coding convention","A branching strategy"],"answer":1,"topic":"DevOps","difficulty":"medium"},
  {"q":"What is dependency injection?","options":["Injecting bugs into code","Providing dependencies to a class from outside","A type of SQL injection","A network protocol"],"answer":1,"topic":"Design Patterns","difficulty":"medium"},
  {"q":"What is the purpose of an index in a database?","options":["Store backup data","Speed up data retrieval","Encrypt data","Compress tables"],"answer":1,"topic":"Databases","difficulty":"easy"},
  {"q":"In Agile, what is a sprint retrospective?","options":["A planning meeting","A meeting to reflect on what went well and what to improve","A demo to stakeholders","A daily standup"],"answer":1,"topic":"Agile","difficulty":"easy"},
  {"q":"What is WebSocket used for?","options":["Static file serving","Full-duplex real-time communication","Email transfer","Database queries"],"answer":1,"topic":"Networking","difficulty":"medium"},
  {"q":"Which caching strategy writes data to cache and DB simultaneously?","options":["Cache-aside","Write-through","Write-back","Read-through"],"answer":1,"topic":"System Design","difficulty":"medium"},
  {"q":"What is a JWT token used for?","options":["Data storage","Stateless authentication","File compression","Code compilation"],"answer":1,"topic":"Security","difficulty":"easy"},
  {"q":"What is eventual consistency?","options":["Immediate consistency everywhere","System will become consistent given enough time","No consistency","Partial consistency"],"answer":1,"topic":"System Design","difficulty":"medium"},
  {"q":"What is test-driven development (TDD)?","options":["Testing after deployment","Writing tests before writing code","Manual testing only","No testing required"],"answer":1,"topic":"Testing","difficulty":"easy"},
  {"q":"What is the Observer design pattern?","options":["One object watches another for state changes","A singleton variant","A sorting pattern","A database pattern"],"answer":0,"topic":"Design Patterns","difficulty":"medium"},
  {"q":"What is a reverse proxy?","options":["A proxy that blocks traffic","A server that forwards requests to backend servers","A VPN","A firewall"],"answer":1,"topic":"Networking","difficulty":"medium"},
  {"q":"What is the purpose of Docker Compose?","options":["Build Docker images","Define and run multi-container applications","Monitor containers","Deploy to Kubernetes"],"answer":1,"topic":"Docker","difficulty":"medium"},
  {"q":"What is memoization?","options":["A type of memory leak","Caching results of expensive function calls","A debugging technique","A logging strategy"],"answer":1,"topic":"Algorithms","difficulty":"medium"},
  {"q":"What is the purpose of a message queue?","options":["Direct synchronous communication","Asynchronous decoupled communication between services","Database replication","File storage"],"answer":1,"topic":"System Design","difficulty":"medium"},
],
"Data Analyst": [
  {"q":"What does the SQL GROUP BY clause do?","options":["Sorts results","Groups rows sharing a property for aggregation","Filters rows","Joins tables"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"Which chart is best for showing proportions of a whole?","options":["Line chart","Pie chart","Scatter plot","Histogram"],"answer":1,"topic":"Visualization","difficulty":"easy"},
  {"q":"In Excel, which function finds a lookup value in a table?","options":["SUM","VLOOKUP","COUNT","IF"],"answer":1,"topic":"Excel","difficulty":"easy"},
  {"q":"What is a p-value in statistics?","options":["The probability of getting results at least as extreme as observed, assuming null hypothesis is true","The mean of the dataset","A correlation coefficient","The standard deviation"],"answer":0,"topic":"Statistics","difficulty":"medium"},
  {"q":"Which Python library is used for data visualization?","options":["Pandas","Matplotlib","SQLAlchemy","Flask"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"What is a KPI?","options":["Key Performance Indicator","Key Python Interface","Kernel Processing Index","Knowledge Pattern Identifier"],"answer":0,"topic":"Business","difficulty":"easy"},
  {"q":"What does a LEFT JOIN return?","options":["Only matching rows","All rows from left table and matching from right","All rows from right table","Cartesian product"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"What is the difference between mean and median?","options":["They are the same","Mean is the average; median is the middle value","Mean is the mode; median is the range","Median is the average; mean is the middle value"],"answer":1,"topic":"Statistics","difficulty":"easy"},
  {"q":"In Tableau, what is a calculated field?","options":["A pre-built metric","A custom field created using formulas","An imported CSV column","A filter"],"answer":1,"topic":"BI Tools","difficulty":"easy"},
  {"q":"What is data normalization?","options":["Deleting duplicates","Scaling data to a standard range","Backing up data","Encrypting data"],"answer":1,"topic":"Data Cleaning","difficulty":"easy"},
  {"q":"Which SQL function counts non-NULL values?","options":["SUM()","COUNT()","AVG()","MAX()"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"What is a correlation coefficient?","options":["A measure of data size","A measure of linear relationship between two variables","A sorting metric","A data type"],"answer":1,"topic":"Statistics","difficulty":"medium"},
  {"q":"What is a pivot table used for?","options":["Data encryption","Summarizing and reorganizing data","Writing macros","Creating charts only"],"answer":1,"topic":"Excel","difficulty":"easy"},
  {"q":"In Power BI, what is DAX?","options":["Data Analysis Expressions","Database Access XML","Dynamic Application Extension","Data Archive eXport"],"answer":0,"topic":"BI Tools","difficulty":"medium"},
  {"q":"What is the purpose of data profiling?","options":["Visualize data","Examine data for quality, structure, and content","Delete data","Encrypt data"],"answer":1,"topic":"Data Cleaning","difficulty":"easy"},
  {"q":"What is an outlier?","options":["A common data point","A data point significantly different from others","A missing value","A duplicate row"],"answer":1,"topic":"Statistics","difficulty":"easy"},
  {"q":"Which Pandas function reads a CSV file?","options":["pd.open_csv()","pd.read_csv()","pd.load_csv()","pd.import_csv()"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"What is A/B testing?","options":["A debugging method","Comparing two versions to see which performs better","A data storage format","A visualization type"],"answer":1,"topic":"Statistics","difficulty":"medium"},
  {"q":"What does ETL stand for?","options":["Extract, Transform, Load","Edit, Transfer, Log","Encode, Translate, Link","Export, Test, Load"],"answer":0,"topic":"ETL","difficulty":"easy"},
  {"q":"In SQL, what is a subquery?","options":["A backup query","A query nested inside another query","A delete operation","A schema definition"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"What is a box plot used to display?","options":["Trends over time","Distribution through quartiles and outliers","Proportions","Correlations"],"answer":1,"topic":"Visualization","difficulty":"easy"},
  {"q":"What is the purpose of the DISTINCT keyword in SQL?","options":["Sort results","Remove duplicate rows from results","Count rows","Group data"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"What is regression analysis?","options":["A classification method","Modeling the relationship between dependent and independent variables","A clustering technique","A data cleaning method"],"answer":1,"topic":"Statistics","difficulty":"medium"},
  {"q":"Which chart type best shows trends over time?","options":["Pie chart","Bar chart","Line chart","Treemap"],"answer":2,"topic":"Visualization","difficulty":"easy"},
  {"q":"What is data wrangling?","options":["Data deletion","Cleaning and transforming raw data into a usable format","Data encryption","Data visualization"],"answer":1,"topic":"Data Cleaning","difficulty":"easy"},
  {"q":"What is the mode in a dataset?","options":["The average","The middle value","The most frequent value","The range"],"answer":2,"topic":"Statistics","difficulty":"easy"},
  {"q":"In SQL, what does COALESCE do?","options":["Joins tables","Returns the first non-NULL value from a list","Sorts data","Deletes NULL values"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"What is a funnel chart used for?","options":["Showing geographic data","Displaying stages in a process and drop-offs","Comparing categories","Showing distributions"],"answer":1,"topic":"Visualization","difficulty":"easy"},
  {"q":"What is the Central Limit Theorem?","options":["Sample means approximate normal distribution as sample size grows","All data is normally distributed","Variance equals zero for large samples","Mean equals median always"],"answer":0,"topic":"Statistics","difficulty":"hard"},
  {"q":"What does the Pandas .groupby() method do?","options":["Sorts data","Groups data for aggregation","Merges dataframes","Drops duplicates"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"What is cohort analysis?","options":["Analyzing all users together","Grouping users by shared characteristics over time","A machine learning technique","A database design method"],"answer":1,"topic":"Business","difficulty":"medium"},
  {"q":"What is a heat map?","options":["A geographic map","A visualization using color intensity to represent values","A type of filter","A data cleaning tool"],"answer":1,"topic":"Visualization","difficulty":"easy"},
  {"q":"What is the difference between COUNT(*) and COUNT(column)?","options":["They are the same","COUNT(*) counts all rows; COUNT(column) counts non-NULL values in that column","COUNT(*) is slower","COUNT(column) counts all rows"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"What is the purpose of INDEX-MATCH in Excel?","options":["Creating charts","Flexible lookup alternative to VLOOKUP","Data validation","Macro recording"],"answer":1,"topic":"Excel","difficulty":"medium"},
  {"q":"What is standard deviation?","options":["The average value","A measure of data spread around the mean","The maximum value","The data range"],"answer":1,"topic":"Statistics","difficulty":"easy"},
],
"DevOps Engineer": [
  {"q":"What is Infrastructure as Code (IaC)?","options":["Writing code in infrastructure","Managing infrastructure through machine-readable definition files","A programming language","A type of database"],"answer":1,"topic":"IaC","difficulty":"easy"},
  {"q":"Which tool is used for container orchestration?","options":["Docker","Kubernetes","Jenkins","Terraform"],"answer":1,"topic":"Kubernetes","difficulty":"easy"},
  {"q":"What does CI in CI/CD stand for?","options":["Code Integration","Continuous Integration","Central Infrastructure","Container Isolation"],"answer":1,"topic":"CI/CD","difficulty":"easy"},
  {"q":"What is a Dockerfile?","options":["A log file","A script with instructions to build a Docker image","A configuration for Kubernetes","A monitoring dashboard"],"answer":1,"topic":"Docker","difficulty":"easy"},
  {"q":"What is Terraform used for?","options":["Application monitoring","Infrastructure provisioning and management","Code testing","Container runtime"],"answer":1,"topic":"IaC","difficulty":"easy"},
  {"q":"In Kubernetes, what is a Pod?","options":["A network policy","The smallest deployable unit containing one or more containers","A storage volume","A node"],"answer":1,"topic":"Kubernetes","difficulty":"easy"},
  {"q":"What is a reverse proxy?","options":["A client-side proxy","A server that forwards requests to backend servers on behalf of clients","A VPN","A firewall rule"],"answer":1,"topic":"Networking","difficulty":"easy"},
  {"q":"What does Prometheus monitor?","options":["Code quality","System and application metrics","Container images","Infrastructure cost"],"answer":1,"topic":"Monitoring","difficulty":"easy"},
  {"q":"What is a Helm chart?","options":["A monitoring dashboard","A package of Kubernetes resources","A Docker image","A CI/CD pipeline"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is the purpose of a health check endpoint?","options":["Test API performance","Verify that a service is running and healthy","Monitor user activity","Backup data"],"answer":1,"topic":"Monitoring","difficulty":"easy"},
  {"q":"What is GitOps?","options":["Using Git for code storage only","Using Git as the single source of truth for infrastructure and deployments","A testing framework","A database versioning tool"],"answer":1,"topic":"CI/CD","difficulty":"medium"},
  {"q":"Which tool is used for secrets management?","options":["GitHub","HashiCorp Vault","Docker Hub","Grafana"],"answer":1,"topic":"Security","difficulty":"medium"},
  {"q":"What is a rolling deployment?","options":["Deploying all at once","Gradually replacing instances of the old version with the new","Reverting to a previous version","Testing in staging only"],"answer":1,"topic":"CI/CD","difficulty":"medium"},
  {"q":"What is the ELK stack?","options":["Elasticsearch, Logstash, Kibana","Envoy, Linux, Kubernetes","Elastic, Lambda, Kafka","Endpoint, Load, Key"],"answer":0,"topic":"Monitoring","difficulty":"easy"},
  {"q":"In Linux, what does chmod 755 mean?","options":["Delete all files","Owner: rwx, Group: r-x, Others: r-x","Read-only for everyone","Full access for everyone"],"answer":1,"topic":"Linux","difficulty":"medium"},
  {"q":"What is a canary deployment?","options":["Deploying to all users","Releasing to a small subset of users before full rollout","A rollback strategy","A testing environment"],"answer":1,"topic":"CI/CD","difficulty":"medium"},
  {"q":"What is the purpose of an ingress controller in Kubernetes?","options":["Manage storage","Manage external access to services in a cluster","Monitor pods","Scale deployments"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is Ansible used for?","options":["Container orchestration","Configuration management and automation","Code compilation","Database management"],"answer":1,"topic":"IaC","difficulty":"easy"},
  {"q":"What is a service mesh?","options":["A network of services with built-in observability, security, and traffic management","A type of VPN","A DNS service","A load balancer"],"answer":0,"topic":"Networking","difficulty":"hard"},
  {"q":"What is the difference between Docker volumes and bind mounts?","options":["They are the same","Volumes are managed by Docker; bind mounts map to host paths directly","Volumes are temporary; bind mounts are persistent","Bind mounts are faster"],"answer":1,"topic":"Docker","difficulty":"medium"},
  {"q":"What is the purpose of a config map in Kubernetes?","options":["Store secrets","Store non-confidential configuration data as key-value pairs","Monitor pods","Manage deployments"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is SRE (Site Reliability Engineering)?","options":["A programming language","Applying software engineering to operations problems","A monitoring tool","A deployment strategy"],"answer":1,"topic":"SRE","difficulty":"easy"},
  {"q":"What is the purpose of a load balancer?","options":["Store sessions","Distribute incoming traffic across multiple servers","Encrypt data","Compile code"],"answer":1,"topic":"Networking","difficulty":"easy"},
  {"q":"What is immutable infrastructure?","options":["Infrastructure that changes frequently","Infrastructure that is never modified after deployment; replaced instead","Temporary infrastructure","Infrastructure without monitoring"],"answer":1,"topic":"IaC","difficulty":"medium"},
  {"q":"What is the purpose of Grafana?","options":["Code review","Visualization and dashboarding for metrics","Container orchestration","CI/CD pipelines"],"answer":1,"topic":"Monitoring","difficulty":"easy"},
  {"q":"What is a multi-stage Docker build?","options":["Running multiple containers","Using multiple FROM statements to reduce image size","Deploying to multiple environments","Building on multiple OS"],"answer":1,"topic":"Docker","difficulty":"medium"},
  {"q":"What is the blue-green deployment strategy?","options":["Using two identical environments and switching traffic between them","Deploying to one server at a time","A testing strategy","A branching model"],"answer":0,"topic":"CI/CD","difficulty":"medium"},
  {"q":"What is the purpose of a liveness probe in Kubernetes?","options":["Check if a pod is ready for traffic","Check if a container is still running","Monitor CPU usage","Scale pods"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What does 'shift left' mean in DevOps?","options":["Move deployment earlier","Integrate testing and security earlier in the development lifecycle","Shift servers to the left region","Reduce team size"],"answer":1,"topic":"CI/CD","difficulty":"easy"},
  {"q":"What is the purpose of a NAT gateway?","options":["Route traffic between containers","Allow private subnet resources to access the internet","Store DNS records","Monitor network traffic"],"answer":1,"topic":"Networking","difficulty":"medium"},
  {"q":"What is the principle of least privilege?","options":["Give everyone admin access","Grant only minimum permissions needed to perform a task","Disable all access by default","Use only one user account"],"answer":1,"topic":"Security","difficulty":"easy"},
  {"q":"What is a DaemonSet in Kubernetes?","options":["A deployment with replicas","Ensures a copy of a pod runs on all (or some) nodes","A service type","A config object"],"answer":1,"topic":"Kubernetes","difficulty":"medium"},
  {"q":"What is the purpose of Terraform state?","options":["Store application logs","Track the current state of managed infrastructure","Configure CI/CD","Monitor performance"],"answer":1,"topic":"IaC","difficulty":"medium"},
  {"q":"What is a container registry?","options":["A runtime environment","A repository for storing and distributing container images","A monitoring tool","A CI/CD pipeline"],"answer":1,"topic":"Docker","difficulty":"easy"},
  {"q":"What is chaos engineering?","options":["Breaking things randomly","Deliberately introducing failures to test system resilience","A debugging technique","A deployment strategy"],"answer":1,"topic":"SRE","difficulty":"medium"},
],
}


# ─────────────────────────────────────────────
# SKILLS DICTIONARY
# ─────────────────────────────────────────────
SKILLS_DICTIONARY = {
    "Programming": ["python","java","javascript","typescript","scala","r","go","rust","c++",
                     "c#","ruby","kotlin","php","swift","perl","bash","shell","powershell"],
    "Databases": ["sql","mysql","postgresql","postgres","mongodb","cassandra","redis",
                  "dynamodb","oracle","snowflake","redshift","bigquery","hive","hbase",
                  "cockroachdb","couchbase","neo4j","elasticsearch"],
    "Cloud": ["aws","azure","gcp","google cloud","s3","ec2","lambda","iam","cloudformation",
              "cloud","sagemaker","emr","glue","athena","kinesis","azure data factory",
              "azure synapse","azure data lake","cloud storage","cloud functions"],
    "Big Data": ["spark","pyspark","hadoop","mapreduce","kafka","flink","hive","presto",
                 "trino","databricks","delta lake","delta","iceberg","lakehouse"],
    "ETL & Orchestration": ["etl","elt","airflow","dbt","nifi","talend","informatica",
                            "mwaa","dagster","prefect","luigi","cron","orchestration",
                            "data pipeline","pipeline","data integration"],
    "DevOps": ["docker","kubernetes","k8s","terraform","ansible","jenkins","github actions",
               "gitlab ci","helm","prometheus","grafana","datadog","elk","logstash",
               "kibana","argocd","flux","istio","nginx"],
    "Data Concepts": ["data modeling","data warehouse","data warehousing","data lake",
                      "data pipeline","data governance","data quality","data catalog",
                      "medallion","star schema","snowflake schema","data vault","scd",
                      "slowly changing dimension","data lineage","metadata","schema on read",
                      "schema on write","olap","oltp","dimensional modeling","normalization"],
    "BI & Visualization": ["tableau","power bi","powerbi","looker","matplotlib","seaborn",
                           "plotly","d3","superset","qlik","sisense","metabase"],
    "Machine Learning": ["machine learning","deep learning","tensorflow","pytorch",
                         "scikit-learn","sklearn","nlp","computer vision","mlops",
                         "neural network","random forest","xgboost","regression",
                         "classification","clustering"],
    "Software Engineering": ["git","agile","scrum","rest api","restful","graphql",
                             "microservices","ci/cd","cicd","tdd","unit testing",
                             "integration testing","design patterns","solid","oop",
                             "functional programming","websocket","jwt","oauth"],
    "Certifications": ["databricks certified","aws certified","google professional",
                       "azure certified","ckad","cka","terraform associate",
                       "certified data engineer","certified developer",
                       "certified solutions architect","pmp","csm","togaf"],
}

# ─────────────────────────────────────────────
# HELPER FUNCTIONS
# ─────────────────────────────────────────────

def add_log(candidate_id, stage, decision, score, reason, next_action, owner="AI_AGENT"):
    entry = {
        "candidate_id": candidate_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stage": stage,
        "decision": decision,
        "score": score,
        "reason": reason,
        "next_action": next_action,
        "owner": owner,
    }
    st.session_state.pipeline_logs.append(entry)
    return entry


def parse_cv_text(uploaded_file):
    if uploaded_file is None:
        return ""
    file_name = uploaded_file.name.lower()
    try:
        if file_name.endswith(".pdf"):
            try:
                import PyPDF2
                reader = PyPDF2.PdfReader(uploaded_file)
                text = ""
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                return text.strip()
            except ImportError:
                return uploaded_file.read().decode("utf-8", errors="ignore")
        elif file_name.endswith(".txt"):
            return uploaded_file.read().decode("utf-8", errors="ignore")
        elif file_name.endswith(".docx"):
            try:
                import docx
                doc = docx.Document(BytesIO(uploaded_file.read()))
                text = "\n".join([para.text for para in doc.paragraphs])
                return text.strip()
            except ImportError:
                return uploaded_file.read().decode("utf-8", errors="ignore")
        else:
            return uploaded_file.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return f"ERROR_PARSING: {str(e)}"


def extract_skills_from_text(text):
    text_lower = text.lower()
    found_skills = {}
    for category, skills in SKILLS_DICTIONARY.items():
        matched = []
        for skill in skills:
            if len(skill) <= 3:
                pattern = r'\b' + re.escape(skill) + r'\b'
                if re.search(pattern, text_lower):
                    matched.append(skill)
            else:
                if skill in text_lower:
                    matched.append(skill)
        if matched:
            found_skills[category] = list(set(matched))
    return found_skills


def extract_experience_years(text):
    patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)',
        r'(?:experience|exp)\s*(?:of)?\s*(\d+)\+?\s*(?:years?|yrs?)',
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:in|of|working)',
        r'(?:over|more than|approximately|approx|about)\s*(\d+)\s*(?:years?|yrs?)',
    ]
    years_found = []
    text_lower = text.lower()
    for pattern in patterns:
        matches = re.findall(pattern, text_lower)
        for m in matches:
            try:
                y = int(m)
                if 0 < y < 50:
                    years_found.append(y)
            except ValueError:
                pass
    return max(years_found) if years_found else 0


def extract_education(text):
    text_lower = text.lower()
    education_keywords = [
        "bachelor", "master", "phd", "doctorate", "b.tech", "m.tech",
        "b.sc", "m.sc", "bsc", "msc", "b.e.", "m.e.", "mba",
        "computer science", "data science", "information technology",
        "information systems", "software engineering", "statistics",
        "mathematics", "electrical engineering", "electronics",
        "engineering", "university", "college", "degree"
    ]
    return [kw for kw in education_keywords if kw in text_lower]


def calculate_ats_score(cv_text, jd_text, role):
    if not cv_text or "ERROR_PARSING" in cv_text:
        return {
            "ats_score": 0, "decision": "FAIL",
            "reasoning_summary": "CV could not be parsed.",
            "matched_skills": [], "missing_skills": [],
            "experience_match": "Unable to determine",
            "strengths": [], "gaps": ["CV parsing failed"],
            "requires_human_review": True,
            "score_breakdown": {"skill_score":0,"experience_score":0,"education_score":0,"certification_score":0,"tool_platform_score":0},
        }

    cv_skills = extract_skills_from_text(cv_text)
    jd_skills = extract_skills_from_text(jd_text)
    cv_exp = extract_experience_years(cv_text)
    jd_exp = extract_experience_years(jd_text)
    cv_edu = extract_education(cv_text)
    jd_edu = extract_education(jd_text)

    cv_set = set()
    for s in cv_skills.values():
        cv_set.update(s)
    jd_set = set()
    for s in jd_skills.values():
        jd_set.update(s)

    # 1. SKILL MATCH (40%)
    if jd_set:
        matched = cv_set & jd_set
        missing = jd_set - cv_set
        skill_pct = len(matched) / len(jd_set)
    else:
        matched = cv_set
        missing = set()
        skill_pct = 0.5
    skill_score = min(skill_pct * 100, 100) * 0.40

    # 2. EXPERIENCE (20%)
    if jd_exp > 0:
        if cv_exp >= jd_exp:
            exp_score = 100 * 0.20
            exp_match = f"CV: {cv_exp} yrs >= JD: {jd_exp} yrs"
        elif cv_exp >= jd_exp * 0.7:
            exp_score = 75 * 0.20
            exp_match = f"CV: {cv_exp} yrs (slightly below JD: {jd_exp} yrs)"
        else:
            exp_score = max(30, (cv_exp / jd_exp) * 100) * 0.20
            exp_match = f"CV: {cv_exp} yrs < JD: {jd_exp} yrs"
    else:
        exp_score = 60 * 0.20
        exp_match = f"CV: {cv_exp} yrs (JD requirement not clearly specified)"

    # 3. EDUCATION (15%)
    if jd_edu:
        edu_pct = len(set(cv_edu) & set(jd_edu)) / len(set(jd_edu))
    else:
        edu_pct = 0.6
    edu_score = min(edu_pct * 100, 100) * 0.15

    # 4. CERTIFICATIONS (10%)
    cv_certs = cv_skills.get("Certifications", [])
    jd_certs = jd_skills.get("Certifications", [])
    if jd_certs:
        cert_pct = len(set(cv_certs) & set(jd_certs)) / len(set(jd_certs))
    else:
        cert_pct = 0.5 if cv_certs else 0.3
    cert_score = min(cert_pct * 100, 100) * 0.10

    # 5. TOOLS/PLATFORM (15%)
    tool_cats = ["Cloud", "Big Data", "DevOps", "BI & Visualization"]
    t_match = t_total = 0
    for cat in tool_cats:
        jt = set(jd_skills.get(cat, []))
        ct = set(cv_skills.get(cat, []))
        t_total += len(jt)
        t_match += len(ct & jt)
    tool_pct = (t_match / t_total) if t_total > 0 else 0.5
    tool_score = min(tool_pct * 100, 100) * 0.15

    total = round(skill_score + exp_score + edu_score + cert_score + tool_score, 1)
    total = min(total, 100)

    strengths = []
    gaps = []
    if jd_set and skill_pct > 0.7:
        strengths.append(f"Strong skill match ({len(matched)}/{len(jd_set)} skills)")
    elif jd_set:
        gaps.append(f"Skill gap: missing {len(missing)} of {len(jd_set)} required skills")
    if cv_exp >= jd_exp and jd_exp > 0:
        strengths.append(f"Meets experience requirement ({cv_exp} yrs)")
    elif jd_exp > 0:
        gaps.append(f"Experience below requirement ({cv_exp} vs {jd_exp} yrs)")
    if edu_pct > 0.5:
        strengths.append("Education aligns with role requirements")
    if cv_certs:
        strengths.append(f"Has relevant certifications: {', '.join(cv_certs)}")
    elif jd_certs:
        gaps.append("No matching certifications found")

    decision = "PASS" if total > 85 else "FAIL"
    requires_review = 75 <= total <= 85

    reasoning = (
        f"ATS Score: {total}/100. "
        f"Skill match: {len(matched)}/{len(jd_set)} required skills found. "
        f"Experience: {exp_match}. "
        f"{'Human review recommended due to borderline score.' if requires_review else ''}"
    )

    return {
        "ats_score": total, "decision": decision,
        "reasoning_summary": reasoning.strip(),
        "matched_skills": sorted(list(matched)),
        "missing_skills": sorted(list(missing)),
        "experience_match": exp_match,
        "strengths": strengths, "gaps": gaps,
        "requires_human_review": requires_review,
        "score_breakdown": {
            "skill_score": round(skill_score, 1),
            "experience_score": round(exp_score, 1),
            "education_score": round(edu_score, 1),
            "certification_score": round(cert_score, 1),
            "tool_platform_score": round(tool_score, 1),
        },
    }


def get_assessment_questions(role, num_questions=30):
    role_key = None
    for key in QUESTION_BANKS:
        if key.lower() in role.lower() or role.lower() in key.lower():
            role_key = key
            break
    if role_key is None:
        role_key = "Software Engineer"
    bank = QUESTION_BANKS[role_key][:]
    random.shuffle(bank)
    return bank[:num_questions]


def score_assessment(questions, answers):
    if not questions or not answers:
        return {"score_percent": 0, "correct": 0, "total": 0, "strength_areas": [], "weak_areas": [], "topic_breakdown": {}}
    correct = 0
    topic_scores = {}
    for i, q in enumerate(questions):
        topic = q.get("topic", "General")
        if topic not in topic_scores:
            topic_scores[topic] = {"correct": 0, "total": 0}
        topic_scores[topic]["total"] += 1
        user_answer = answers.get(str(i), None)
        if user_answer is not None and int(user_answer) == q["answer"]:
            correct += 1
            topic_scores[topic]["correct"] += 1
    total = len(questions)
    score_percent = round((correct / total) * 100, 1) if total > 0 else 0
    strength_areas = []
    weak_areas = []
    for topic, data in topic_scores.items():
        pct = (data["correct"] / data["total"]) * 100 if data["total"] > 0 else 0
        if pct >= 75:
            strength_areas.append(f"{topic} ({data['correct']}/{data['total']})")
        elif pct < 50:
            weak_areas.append(f"{topic} ({data['correct']}/{data['total']})")
    return {"score_percent": score_percent, "correct": correct, "total": total,
            "strength_areas": strength_areas, "weak_areas": weak_areas, "topic_breakdown": topic_scores}


def get_panel_availability(role):
    panels = {
        "Data Engineer": [{"name": "Mena Suresh", "title": "Senior Data Engineer"}, {"name": "James Chen", "title": "Data Engineering Manager"}],
        "Software Engineer": [{"name": "Alex Rivera", "title": "Staff Software Engineer"}, {"name": "Sarah Kim", "title": "Engineering Manager"}],
        "Data Analyst": [{"name": "Michael Brown", "title": "Lead Data Analyst"}, {"name": "Emily Zhang", "title": "Analytics Manager"}],
        "DevOps Engineer": [{"name": "Raj Patel", "title": "Senior DevOps Engineer"}, {"name": "Lisa Johnson", "title": "Platform Engineering Lead"}],
    }
    role_key = None
    for key in panels:
        if key.lower() in role.lower() or role.lower() in key.lower():
            role_key = key
            break
    if role_key is None:
        role_key = "Software Engineer"
    panel = panels[role_key]
    today = datetime.now()
    slots = []
    slot_times = ["09:00 AM", "10:30 AM", "11:30 AM", "01:00 PM", "02:30 PM", "03:30 PM", "04:00 PM"]
    for day_offset in range(1, 4):
        day = today + timedelta(days=day_offset)
        day_str = day.strftime("%A, %B %d, %Y")
        available = random.sample(slot_times, k=random.randint(2, 4))
        available.sort()
        for slot_time in available:
            slots.append({"date": day_str, "time": slot_time, "duration": "45 minutes",
                          "mode": "Video Call (Microsoft Teams)", "panel": [p["name"] for p in panel], "timezone": "UTC"})
    return {"panel": panel, "slots": slots}


def generate_rejection_email(candidate_name, role, stage, recruiter_name):
    if stage == "ATS":
        return f"""Subject: Update on Your Application for {role}

Dear {candidate_name},

Thank you for your interest in the {role} position and for taking the time to apply.

After reviewing your profile, we will not be moving forward with your application for this role at this stage.

We appreciate your interest in our opportunity and encourage you to apply again for future roles that match your experience.

Wishing you all the best in your job search.

Best regards,
{recruiter_name}"""
    else:
        return f"""Subject: Update on Your Application for {role}

Dear {candidate_name},

Thank you for completing the assessment for the {role} role.

After careful evaluation, we will not be moving forward with your application to the next stage.

We appreciate the time and effort you invested in the process and wish you success in your future opportunities.

Best regards,
{recruiter_name}"""


def generate_assessment_email(candidate_name, role, deadline, recruiter_name):
    link = f"https://assess.talentedge.ai/{hashlib.md5(candidate_name.encode()).hexdigest()[:12]}"
    return f"""Subject: Next Step: Assessment for {role}

Dear {candidate_name},

Thank you for your application for the {role} role.

We are pleased to invite you to complete the next stage of the selection process: an online assessment.

Assessment Details:
- Number of questions: 30
- Duration: 20 minutes
- Link: {link}
- Deadline: {deadline}

Important Instructions:
- Complete the assessment in one sitting.
- Ensure a stable internet connection.
- The assessment runs in full-screen mode.
- Do not switch tabs or windows during the test.
- Copy-paste and tab-switching will be monitored.
- Any suspicious activity will be flagged for review.

If you face any technical difficulties, please reply to this email.

Best regards,
{recruiter_name}"""


def generate_interview_email(candidate_name, role, slots, recruiter_name):
    link = f"https://schedule.talentedge.ai/{hashlib.md5(candidate_name.encode()).hexdigest()[:12]}"
    slot_lines = ""
    for i, slot in enumerate(slots[:6], 1):
        slot_lines += f"  - Slot {i}: {slot['date']} at {slot['time']} ({slot['duration']}, {slot['timezone']})\n"
    return f"""Subject: Interview Scheduling for {role}

Dear {candidate_name},

Congratulations! You have successfully cleared the assessment stage for the {role} position.

We would like to invite you to schedule your interview. Please choose one of the available slots:

{slot_lines}
Interview Details:
- Mode: Video Call (Microsoft Teams)
- Duration: 45 minutes
- Scheduling Link: {link}

If none of these slots work for you, please reply to this email and our team will assist you.

Best regards,
{recruiter_name}"""


# ─────────────────────────────────────────────
# STREAMLIT SIDEBAR
# ─────────────────────────────────────────────
st.sidebar.markdown("# \U0001f916 AI Recruitment Agent")
st.sidebar.markdown("**Automated Pre-Screening Workflow**")
st.sidebar.markdown("---")

page = st.sidebar.radio(
    "Navigation",
    ["\U0001f4c4 CV Upload & ATS", "\U0001f4dd Assessment", "\U0001f4ca Results & Interview",
     "\U0001f4cb Pipeline Logs", "\U0001f4e7 Email Log", "\U0001f464 Candidate Dashboard"],
    index=0,
)

# ── Email Configuration ──
st.sidebar.markdown("---")
st.sidebar.markdown("### \U0001f4e7 Email Automation")
st.session_state.auto_email_enabled = st.sidebar.checkbox(
    "Enable Auto Email Sending", value=st.session_state.auto_email_enabled,
    help="When enabled, emails are sent automatically at each pipeline stage."
)

with st.sidebar.expander("\u2699\ufe0f SMTP Configuration"):
    st.session_state.smtp_server = st.text_input("SMTP Server", value=st.session_state.smtp_server, key="sb_smtp_server")
    st.session_state.smtp_port = st.number_input("SMTP Port", value=st.session_state.smtp_port, min_value=1, max_value=65535, key="sb_smtp_port")
    st.session_state.sender_email = st.text_input("Sender Email", value=st.session_state.sender_email, key="sb_sender_email")
    st.session_state.sender_password = st.text_input("Sender Password (App Password)", value=st.session_state.sender_password, type="password", key="sb_sender_pwd")

    if st.session_state.sender_email and st.session_state.sender_password:
        st.session_state.smtp_configured = True
    else:
        st.session_state.smtp_configured = False

    if st.button("\U0001f50c Test SMTP Connection"):
        if not st.session_state.smtp_configured:
            st.error("Please fill in sender email and password first.")
        else:
            try:
                with smtplib.SMTP(st.session_state.smtp_server, st.session_state.smtp_port, timeout=10) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(st.session_state.sender_email, st.session_state.sender_password)
                st.success("\u2705 SMTP connection successful!")
            except Exception as e:
                st.error(f"\u274c Connection failed: {str(e)}")

    st.info("""
    **Gmail users:** Use an [App Password](https://myaccount.google.com/apppasswords) instead of your regular password.

    **Outlook/Hotmail:** smtp-mail.outlook.com, port 587
    **Yahoo:** smtp.mail.yahoo.com, port 587
    """)

    # Status indicator
    if st.session_state.smtp_configured and st.session_state.auto_email_enabled:
        st.success("\U0001f7e2 Auto-email: ACTIVE")
    elif st.session_state.auto_email_enabled and not st.session_state.smtp_configured:
        st.warning("\U0001f7e1 Auto-email ON but SMTP not configured. Emails will be QUEUED.")
    else:
        st.info("\u26aa Auto-email: DISABLED. Emails generated as previews only.")

st.sidebar.markdown("---")
st.sidebar.markdown("### \u2699\ufe0f Recruiter Settings")
st.session_state.recruiter_name = st.sidebar.text_input("Recruiter / Team Name", value=st.session_state.recruiter_name)
st.session_state.recruiter_email = st.sidebar.text_input("Recruiter Email", value=st.session_state.recruiter_email)

if st.session_state.current_candidate_id and st.session_state.current_candidate_id in st.session_state.candidates:
    cand = st.session_state.candidates[st.session_state.current_candidate_id]
    st.sidebar.markdown("---")
    st.sidebar.markdown("### \U0001f464 Active Candidate")
    st.sidebar.markdown(f"**Name:** {cand.get('name','N/A')}")
    st.sidebar.markdown(f"**Role:** {cand.get('role','N/A')}")
    status = cand.get("status", "Pending")
    status_color = {"Passed ATS": "\U0001f7e2", "Failed ATS": "\U0001f534", "Assessment Sent": "\U0001f7e1",
                    "Passed Assessment": "\U0001f7e2", "Failed Assessment": "\U0001f534",
                    "Interview Scheduled": "\U0001f7e2", "Manual Review": "\U0001f7e0"}.get(status, "\u26aa")
    st.sidebar.markdown(f"**Status:** {status_color} {status}")

if st.sidebar.button("\U0001f504 Reset All Data"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()


# helper to display automation results
def show_automation_results(actions):
    """Display automation action results in the UI."""
    if not actions:
        return
    st.markdown("### \u26a1 Automation Actions")
    for act in actions:
        icon = "\u2705" if act["status"] == "SENT" else ("\U0001f7e1" if act["status"] == "QUEUED" else "\u274c")
        st.markdown(f"{icon} **{act['action']}** \u2192 `{act['to']}` — **{act['status']}**")
        if act["status"] != "SENT":
            st.caption(f"   {act['detail']}")


# ═════════════════════════════════════════════
# PAGE 1: CV UPLOAD & ATS ANALYSIS
# ═════════════════════════════════════════════
if page == "\U0001f4c4 CV Upload & ATS":
    st.markdown("# \U0001f4c4 CV Upload & ATS Screening")
    st.markdown("Upload a candidate\u2019s CV and analyze it against the job description. **All follow-up emails are sent automatically.**")
    st.markdown("---")

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        st.markdown("### \U0001f464 Candidate Information")
        c_id = st.text_input("Candidate ID", value=f"CAND-{datetime.now().strftime('%Y%m%d%H%M%S')}", help="Auto-generated or enter manually")
        c_name = st.text_input("Candidate Name", placeholder="e.g., John Doe")
        c_email = st.text_input("Candidate Email", placeholder="e.g., john.doe@email.com")

        role_options = list(JD_TEMPLATES.keys()) + ["Custom Role"]
        role_applied = st.selectbox("Role Applied For", role_options)
        if role_applied == "Custom Role":
            role_applied = st.text_input("Enter Custom Role Title", placeholder="e.g., ML Engineer")

        st.markdown("### \U0001f4ce Upload CV")
        uploaded_cv = st.file_uploader("Upload CV (PDF, TXT, DOCX)", type=["pdf", "txt", "docx"])
        cv_text_manual = st.text_area("Or paste CV text here", height=200, placeholder="Paste the candidate's CV content here...")

    with col_right:
        st.markdown("### \U0001f4cb Job Description")
        if role_applied in JD_TEMPLATES:
            jd_text = st.text_area("Job Description", value=JD_TEMPLATES[role_applied], height=400)
        else:
            jd_text = st.text_area("Enter Job Description", height=400, placeholder="Paste the full job description here...")

        with st.expander("\u2139\ufe0f Scoring Methodology"):
            st.markdown("""
            | Component | Weight |
            |---|---|
            | Skill Match | 40% |
            | Experience | 20% |
            | Education | 15% |
            | Certifications | 10% |
            | Tools / Platforms | 15% |

            **Pass threshold: > 85%** \u00b7 Borderline (75\u201385%) flagged for human review.
            """)

    st.markdown("---")

    # Automation status banner
    if st.session_state.auto_email_enabled and st.session_state.smtp_configured:
        st.success("\u26a1 **Auto-email is ACTIVE.** Rejection / Assessment emails will be sent automatically after ATS analysis.")
    elif st.session_state.auto_email_enabled:
        st.warning("\u26a1 Auto-email is enabled but SMTP is not configured. Emails will be queued (preview only).")
    else:
        st.info("\U0001f4e7 Auto-email is disabled. Emails will be generated as previews for manual sending.")

    if st.button("\U0001f50d Analyze CV & Generate ATS Score", type="primary", use_container_width=True):
        if not c_name:
            st.error("\u274c Please enter the candidate's name.")
        elif not c_email:
            st.error("\u274c Please enter the candidate's email address for automated communication.")
        elif not jd_text.strip():
            st.error("\u274c Please provide a job description.")
        else:
            cv_text = ""
            if uploaded_cv:
                with st.spinner("Parsing CV..."):
                    cv_text = parse_cv_text(uploaded_cv)
            if not cv_text and cv_text_manual.strip():
                cv_text = cv_text_manual.strip()

            if not cv_text:
                st.error("\u274c No CV content found. Please upload a file or paste the CV text.")
            else:
                with st.spinner("\U0001f504 Analyzing CV against Job Description..."):
                    result = calculate_ats_score(cv_text, jd_text, role_applied)

                candidate_data = {
                    "id": c_id, "name": c_name, "email": c_email, "role": role_applied,
                    "cv_text": cv_text[:500] + "..." if len(cv_text) > 500 else cv_text,
                    "ats_result": result,
                    "status": "Passed ATS" if result["decision"] == "PASS" else ("Manual Review" if result["requires_human_review"] else "Failed ATS"),
                    "assessment_result": None, "interview_scheduled": False, "emails_sent": [],
                    "interview_slots": [], "interview_panel": [],
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                st.session_state.candidates[c_id] = candidate_data
                st.session_state.current_candidate_id = c_id

                st.markdown("---")
                st.markdown("## \U0001f4ca ATS Screening Results")

                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    delta_text = "\u2705 PASS" if result["decision"] == "PASS" else "\u274c FAIL"
                    delta_color = "normal" if result["decision"] == "PASS" else "inverse"
                    st.metric("ATS Score", f"{result['ats_score']}/100", delta=delta_text, delta_color=delta_color)
                with m2:
                    st.metric("Matched Skills", len(result["matched_skills"]))
                with m3:
                    st.metric("Missing Skills", len(result["missing_skills"]))
                with m4:
                    st.metric("Decision", result["decision"])

                with st.expander("\U0001f4c8 Score Breakdown", expanded=True):
                    breakdown = result.get("score_breakdown", {})
                    for component, score in breakdown.items():
                        label = component.replace("_", " ").title()
                        max_map = {"skill_score": 40, "experience_score": 20, "education_score": 15, "certification_score": 10, "tool_platform_score": 15}
                        max_val = max_map.get(component, 20)
                        pct = min(score / max_val, 1.0) if max_val > 0 else 0
                        st.markdown(f"**{label}**: {score}/{max_val}")
                        st.progress(pct)

                sk1, sk2 = st.columns(2)
                with sk1:
                    st.markdown("#### \u2705 Matched Skills")
                    if result["matched_skills"]:
                        st.markdown(" ".join([f'`{s}`' for s in result["matched_skills"]]))
                    else:
                        st.info("No matched skills found.")
                with sk2:
                    st.markdown("#### \u274c Missing Skills")
                    if result["missing_skills"]:
                        st.markdown(" ".join([f'`{s}`' for s in result["missing_skills"]]))
                    else:
                        st.success("No gaps identified!")

                sg1, sg2 = st.columns(2)
                with sg1:
                    st.markdown("#### \U0001f4aa Strengths")
                    for s in result.get("strengths", []):
                        st.markdown(f"- {s}")
                with sg2:
                    st.markdown("#### \u26a0\ufe0f Gaps")
                    for g in result.get("gaps", []):
                        st.markdown(f"- {g}")

                st.markdown(f"**\U0001f4c5 Experience Match:** {result.get('experience_match', 'N/A')}")

                with st.expander("\U0001f527 Full ATS JSON Output"):
                    json_output = {
                        "candidate_id": c_id, "stage": "ATS_SCREENING", "ats_score": result["ats_score"],
                        "decision": result["decision"], "reasoning_summary": result["reasoning_summary"],
                        "matched_skills": result["matched_skills"], "missing_skills": result["missing_skills"],
                        "experience_match": result["experience_match"],
                        "recommended_next_action": "Send Assessment" if result["decision"] == "PASS" else "Send Rejection Email",
                        "requires_human_review": result["requires_human_review"],
                    }
                    st.json(json_output)

                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                # AUTOMATED ACTIONS
                # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                st.markdown("---")
                if result["decision"] == "PASS":
                    st.success(f"\U0001f389 **{c_name}** has PASSED the ATS screening with a score of **{result['ats_score']}%**!")
                    add_log(c_id, "ATS_SCREENING", "PASS", result["ats_score"], result["reasoning_summary"], "Send Assessment (Auto)", "AI_AGENT")

                    # AUTO: Send assessment + Notify recruiter
                    with st.spinner("\u26a1 Sending assessment invitation & recruiter notification..."):
                        actions = auto_pipeline_action(candidate_data, "ats_pass")

                    candidate_data["status"] = "Assessment Sent"
                    st.session_state.candidates[c_id] = candidate_data
                    show_automation_results(actions)

                    # Show email preview
                    for em in candidate_data.get("emails_sent", []):
                        with st.expander(f"\U0001f4e7 {em['type']} \u2014 {em.get('send_status','N/A')}"):
                            st.code(em["content"], language="text")

                    st.info("\U0001f449 Navigate to **\U0001f4dd Assessment** page to proceed with the assessment.")

                elif result["requires_human_review"]:
                    st.warning(f"\u26a0\ufe0f **{c_name}** scored **{result['ats_score']}%** \u2014 borderline. Flagged for **human recruiter review**.")
                    add_log(c_id, "ATS_SCREENING", "REVIEW", result["ats_score"], "Borderline score; requires human review", "Escalate to Recruiter", "AI_AGENT")
                else:
                    st.error(f"\u274c **{c_name}** has NOT passed the ATS screening (Score: **{result['ats_score']}%**).")
                    add_log(c_id, "ATS_SCREENING", "FAIL", result["ats_score"], result["reasoning_summary"], "Send Rejection (Auto)", "AI_AGENT")

                    # AUTO: Send rejection + Notify recruiter
                    with st.spinner("\u26a1 Sending rejection email & recruiter notification..."):
                        actions = auto_pipeline_action(candidate_data, "ats_fail")

                    st.session_state.candidates[c_id] = candidate_data
                    show_automation_results(actions)

                    for em in candidate_data.get("emails_sent", []):
                        with st.expander(f"\U0001f4e7 {em['type']} \u2014 {em.get('send_status','N/A')}"):
                            st.code(em["content"], language="text")


# ═════════════════════════════════════════════
# PAGE 2: ASSESSMENT
# ═════════════════════════════════════════════
elif page == "\U0001f4dd Assessment":
    st.markdown("# \U0001f4dd Role-Specific Assessment")

    cid = st.session_state.current_candidate_id
    if not cid or cid not in st.session_state.candidates:
        st.warning("\u26a0\ufe0f No active candidate. Please complete the ATS screening first on the **\U0001f4c4 CV Upload & ATS** page.")
    else:
        cand = st.session_state.candidates[cid]
        status = cand.get("status", "")

        if status in ["Failed ATS"]:
            st.error("\u274c This candidate did not pass the ATS stage and is not eligible for the assessment.")
        elif status in ["Passed Assessment", "Failed Assessment", "Interview Scheduled"]:
            st.info(f"\u2139\ufe0f Assessment already completed. Current status: **{status}**. Check **\U0001f4ca Results & Interview**.")
        else:
            st.markdown(f"**Candidate:** {cand['name']} | **Role:** {cand['role']} | **ATS Score:** {cand['ats_result']['ats_score']}%")
            st.markdown("---")

            with st.expander("\U0001f4cb Assessment Instructions & Anti-Cheating Notice", expanded=not st.session_state.assessment_started):
                st.markdown("""
                **Assessment Details:**
                - **Questions:** 30 multiple-choice questions
                - **Duration:** 20 minutes
                - **Pass Threshold:** > 90%
                - **Topics:** Role-specific technical and practical questions

                **\u26a0\ufe0f Anti-Cheating Policy:**
                - Complete the assessment in **one sitting**.
                - The assessment runs in **full-screen mode** where supported.
                - **Do NOT** switch tabs, windows, or applications.
                - **Copy-paste** actions are monitored and logged.
                - **Tab switching**, idle time, and unusual answer patterns will be flagged.
                - If suspicious activity is detected, your attempt will be flagged for review.

                By starting the assessment, you acknowledge and consent to the above monitoring policies.
                """)

            if not st.session_state.assessment_started:
                if st.button("\U0001f680 Start Assessment", type="primary", use_container_width=True):
                    questions = get_assessment_questions(cand["role"], 30)
                    st.session_state.assessment_questions = questions
                    st.session_state.assessment_started = True
                    st.session_state.assessment_answers = {}
                    st.session_state.assessment_submitted = False
                    st.session_state.assessment_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    add_log(cid, "ASSESSMENT_STARTED", "IN_PROGRESS", "N/A",
                            "Candidate started the assessment", "Awaiting submission", "AI_AGENT")
                    st.rerun()
            else:
                questions = st.session_state.get("assessment_questions", [])
                if not questions:
                    st.error("Error loading questions. Please restart the assessment.")
                elif not st.session_state.assessment_submitted:
                    start_time = st.session_state.get("assessment_start_time", "")
                    st.info(f"\u23f1\ufe0f **Started at:** {start_time} | **Duration:** 20 minutes | **Questions:** {len(questions)}")
                    st.markdown("---")
                    for i, q in enumerate(questions):
                        st.markdown(f"**Q{i+1}.** ({q.get('topic','')}, {q.get('difficulty','')}) {q['q']}")
                        key = f"assess_q_{i}"
                        options = q["options"]
                        answer = st.radio(
                            f"Select your answer for Q{i+1}:",
                            options=options, key=key, index=None, label_visibility="collapsed",
                        )
                        if answer is not None:
                            st.session_state.assessment_answers[str(i)] = options.index(answer)
                        st.markdown("---")

                    answered = len(st.session_state.assessment_answers)
                    st.markdown(f"**Answered:** {answered} / {len(questions)}")
                    st.progress(answered / len(questions))

                    if st.button("\u2705 Submit Assessment", type="primary", use_container_width=True):
                        if answered < len(questions):
                            st.warning(f"\u26a0\ufe0f You have answered {answered}/{len(questions)} questions. Unanswered will be marked incorrect.")
                        st.session_state.assessment_submitted = True
                        result = score_assessment(questions, st.session_state.assessment_answers)
                        st.session_state.assessment_result = result
                        decision = "PASS" if result["score_percent"] > 90 else "FAIL"
                        result["decision"] = decision
                        cand["assessment_result"] = result
                        cand["status"] = "Passed Assessment" if decision == "PASS" else "Failed Assessment"

                        add_log(cid, "ASSESSMENT", decision, result["score_percent"],
                                f"Score: {result['correct']}/{result['total']} ({result['score_percent']}%)",
                                "Move to Interview (Auto)" if decision == "PASS" else "Send Rejection (Auto)", "AI_AGENT")

                        # ━━━ AUTO PIPELINE ━━━
                        if decision == "PASS":
                            actions = auto_pipeline_action(cand, "assessment_pass")
                            cand["status"] = "Interview Scheduled"
                        else:
                            actions = auto_pipeline_action(cand, "assessment_fail")

                        cand["auto_actions_assessment"] = actions
                        st.session_state.candidates[cid] = cand
                        st.rerun()
                else:
                    result = st.session_state.get("assessment_result", cand.get("assessment_result", {}))
                    decision = result.get("decision", "FAIL")
                    st.markdown("## \U0001f4ca Assessment Results")
                    r1, r2, r3 = st.columns(3)
                    with r1:
                        st.metric("Score", f"{result.get('score_percent', 0)}%",
                                  delta="\u2705 PASS" if decision == "PASS" else "\u274c FAIL",
                                  delta_color="normal" if decision == "PASS" else "inverse")
                    with r2:
                        st.metric("Correct Answers", f"{result.get('correct',0)}/{result.get('total',0)}")
                    with r3:
                        st.metric("Decision", decision)

                    with st.expander("\U0001f4c8 Topic Breakdown", expanded=True):
                        for topic, data in result.get("topic_breakdown", {}).items():
                            pct = (data["correct"]/data["total"]*100) if data["total"] > 0 else 0
                            st.markdown(f"**{topic}**: {data['correct']}/{data['total']} ({pct:.0f}%)")
                            st.progress(min(pct/100, 1.0))

                    s1, s2 = st.columns(2)
                    with s1:
                        st.markdown("#### \U0001f4aa Strong Areas")
                        for s in result.get("strength_areas", []):
                            st.markdown(f"- \u2705 {s}")
                        if not result.get("strength_areas"):
                            st.info("No strong areas identified.")
                    with s2:
                        st.markdown("#### \u26a0\ufe0f Weak Areas")
                        for w in result.get("weak_areas", []):
                            st.markdown(f"- \u274c {w}")
                        if not result.get("weak_areas"):
                            st.success("No weak areas!")

                    # Show automation results
                    auto_acts = cand.get("auto_actions_assessment", [])
                    if auto_acts:
                        st.markdown("---")
                        show_automation_results(auto_acts)

                    # Show emails
                    for em in cand.get("emails_sent", []):
                        with st.expander(f"\U0001f4e7 {em['type']} \u2014 {em.get('send_status','N/A')}"):
                            st.code(em["content"], language="text")

                    st.info("\U0001f449 Navigate to **\U0001f4ca Results & Interview** for full details.")


# ═════════════════════════════════════════════
# PAGE 3: RESULTS & INTERVIEW
# ═════════════════════════════════════════════
elif page == "\U0001f4ca Results & Interview":
    st.markdown("# \U0001f4ca Results & Interview Scheduling")

    cid = st.session_state.current_candidate_id
    if not cid or cid not in st.session_state.candidates:
        st.warning("\u26a0\ufe0f No active candidate. Please complete the earlier stages first.")
    else:
        cand = st.session_state.candidates[cid]
        st.markdown(f"**Candidate:** {cand['name']} | **Role:** {cand['role']} | **Status:** {cand['status']}")
        st.markdown("---")

        with st.expander("\U0001f4c4 ATS Screening Summary", expanded=False):
            ats = cand.get("ats_result", {})
            if ats:
                st.metric("ATS Score", f"{ats.get('ats_score', 0)}/100", delta=ats.get("decision", "N/A"))
                st.markdown(f"**Reasoning:** {ats.get('reasoning_summary', 'N/A')}")

        assessment = cand.get("assessment_result")
        if assessment:
            with st.expander("\U0001f4dd Assessment Summary", expanded=True):
                a1, a2, a3 = st.columns(3)
                with a1:
                    st.metric("Assessment Score", f"{assessment.get('score_percent', 0)}%")
                with a2:
                    st.metric("Result", assessment.get("decision", "N/A"))
                with a3:
                    st.metric("Correct", f"{assessment.get('correct',0)}/{assessment.get('total',0)}")

            if assessment.get("decision") == "PASS":
                st.success("\U0001f389 Candidate has cleared the assessment! Interview has been automatically scheduled.")
                st.markdown("---")
                st.markdown("## \U0001f5d3\ufe0f Interview Scheduling")

                # Use saved panel and slots from automation
                panel = cand.get("interview_panel", [])
                slots = cand.get("interview_slots", [])

                if not panel or not slots:
                    # Fallback: generate fresh
                    availability = get_panel_availability(cand["role"])
                    panel = availability["panel"]
                    slots = availability["slots"]

                st.markdown("### \U0001f465 Interview Panel")
                for p in panel:
                    st.markdown(f"- **{p['name']}** \u2014 {p['title']}")

                st.markdown("### \U0001f4c5 Available Slots (Next 3 Days)")
                if slots:
                    slot_df = pd.DataFrame(slots)
                    slot_df["panel"] = slot_df["panel"].apply(lambda x: ", ".join(x) if isinstance(x, list) else x)
                    st.dataframe(slot_df, use_container_width=True, hide_index=True)

                if cand.get("interview_scheduled"):
                    st.markdown("---")
                    st.success("\u2705 Interview invitation has been sent automatically. Status updated.")

            elif assessment.get("decision") == "FAIL":
                st.error(f"\u274c Candidate scored **{assessment.get('score_percent', 0)}%** and did not pass (threshold: >90%).")
                st.info("\U0001f4e7 A rejection email was sent automatically.")
        else:
            st.info("\u2139\ufe0f Assessment not yet completed. Please complete it on the **\U0001f4dd Assessment** page.")

        # All emails
        emails = cand.get("emails_sent", [])
        if emails:
            st.markdown("---")
            st.markdown("### \U0001f4ec All Emails for This Candidate")
            for i, em in enumerate(emails):
                status_icon = "\u2705" if em.get("send_status") == "SENT" else ("\U0001f7e1" if em.get("send_status") == "QUEUED" else "\u274c")
                with st.expander(f"{status_icon} {em['type']} \u2014 {em['timestamp']} \u2014 **{em.get('send_status', 'N/A')}**"):
                    st.code(em["content"], language="text")

        # Show automation actions if any
        auto_acts = cand.get("auto_actions_assessment", [])
        if auto_acts:
            st.markdown("---")
            show_automation_results(auto_acts)


# ═════════════════════════════════════════════
# PAGE 4: PIPELINE LOGS
# ═════════════════════════════════════════════
elif page == "\U0001f4cb Pipeline Logs":
    st.markdown("# \U0001f4cb Pipeline Decision Logs")
    st.markdown("Audit trail of all screening decisions with timestamps and reasoning.")
    st.markdown("---")

    logs = st.session_state.pipeline_logs

    if not logs:
        st.info("No pipeline logs yet. Process a candidate to generate logs.")
    else:
        all_cids = list(set(l["candidate_id"] for l in logs))
        filter_cid = st.selectbox("Filter by Candidate ID", ["All"] + all_cids)
        filtered = logs if filter_cid == "All" else [l for l in logs if l["candidate_id"] == filter_cid]

        df = pd.DataFrame(filtered)
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.markdown("### \U0001f4c8 Stage Timeline")
        for log in filtered:
            icon = {
                "PASS": "\U0001f7e2", "FAIL": "\U0001f534", "REVIEW": "\U0001f7e0",
                "IN_PROGRESS": "\U0001f535", "SCHEDULED": "\U0001f7e2", "ESCALATED": "\U0001f7e1"
            }.get(log["decision"], "\u26aa")
            st.markdown(f"{icon} **[{log['timestamp']}]** `{log['stage']}` \u2014 **{log['decision']}** (Score: {log['score']}) \u2192 {log['next_action']} _{log['owner']}_")

        st.markdown("---")
        json_str = json.dumps(filtered, indent=2)
        st.download_button("\U0001f4e5 Download Logs as JSON", data=json_str,
                           file_name=f"pipeline_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                           mime="application/json")


# ═════════════════════════════════════════════
# PAGE 5: EMAIL LOG
# ═════════════════════════════════════════════
elif page == "\U0001f4e7 Email Log":
    st.markdown("# \U0001f4e7 Email Automation Log")
    st.markdown("Track all automated emails sent, failed, or queued across the pipeline.")
    st.markdown("---")

    email_log = st.session_state.email_log

    if not email_log:
        st.info("No emails have been processed yet. Run a candidate through the pipeline to generate email logs.")
    else:
        # Summary metrics
        total = len(email_log)
        sent = sum(1 for e in email_log if e["status"] == "SENT")
        failed = sum(1 for e in email_log if e["status"] == "FAILED")
        queued = sum(1 for e in email_log if e["status"] == "QUEUED")

        em1, em2, em3, em4 = st.columns(4)
        with em1:
            st.metric("Total Emails", total)
        with em2:
            st.metric("\u2705 Sent", sent)
        with em3:
            st.metric("\u274c Failed", failed)
        with em4:
            st.metric("\U0001f7e1 Queued", queued)

        st.markdown("---")

        # Filter
        status_filter = st.selectbox("Filter by Status", ["All", "SENT", "FAILED", "QUEUED"])
        if status_filter == "All":
            filtered_emails = email_log
        else:
            filtered_emails = [e for e in email_log if e["status"] == status_filter]

        if filtered_emails:
            df = pd.DataFrame(filtered_emails)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info(f"No emails with status '{status_filter}'.")

        # Download
        st.markdown("---")
        json_str = json.dumps(email_log, indent=2)
        st.download_button("\U0001f4e5 Download Email Log as JSON", data=json_str,
                           file_name=f"email_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                           mime="application/json")


# ═════════════════════════════════════════════
# PAGE 6: CANDIDATE DASHBOARD
# ═════════════════════════════════════════════
elif page == "\U0001f464 Candidate Dashboard":
    st.markdown("# \U0001f464 Candidate Dashboard")
    st.markdown("Overview of all candidates processed through the recruitment pipeline.")
    st.markdown("---")

    candidates = st.session_state.candidates

    if not candidates:
        st.info("No candidates processed yet. Upload a CV on the **\U0001f4c4 CV Upload & ATS** page to get started.")
    else:
        total = len(candidates)
        passed_ats = sum(1 for c in candidates.values() if c.get("ats_result", {}).get("decision") == "PASS")
        passed_assess = sum(1 for c in candidates.values() if c.get("assessment_result") and c["assessment_result"].get("decision") == "PASS")
        interviews = sum(1 for c in candidates.values() if c.get("interview_scheduled"))

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            st.metric("Total Candidates", total)
        with m2:
            st.metric("Passed ATS", passed_ats)
        with m3:
            st.metric("Passed Assessment", passed_assess)
        with m4:
            st.metric("Interviews Scheduled", interviews)

        st.markdown("---")

        for cid_key, cand_val in candidates.items():
            status = cand_val.get("status", "Unknown")
            status_icon = {
                "Passed ATS": "\U0001f7e2", "Failed ATS": "\U0001f534", "Assessment Sent": "\U0001f7e1",
                "Passed Assessment": "\U0001f7e2", "Failed Assessment": "\U0001f534",
                "Interview Scheduled": "\u2705", "Manual Review": "\U0001f7e0"
            }.get(status, "\u26aa")
            with st.expander(f"{status_icon} **{cand_val['name']}** \u2014 {cand_val['role']} \u2014 {status}", expanded=False):
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown(f"**ID:** {cid_key}")
                    st.markdown(f"**Email:** {cand_val.get('email', 'N/A')}")
                    st.markdown(f"**Created:** {cand_val.get('created_at', 'N/A')}")
                with c2:
                    ats_r = cand_val.get("ats_result", {})
                    st.markdown(f"**ATS Score:** {ats_r.get('ats_score', 'N/A')}")
                    st.markdown(f"**ATS Decision:** {ats_r.get('decision', 'N/A')}")
                with c3:
                    assess_r = cand_val.get("assessment_result") or {}
                    st.markdown(f"**Assessment Score:** {assess_r.get('score_percent', 'N/A')}")
                    st.markdown(f"**Assessment Decision:** {assess_r.get('decision', 'N/A')}")
                    st.markdown(f"**Interview:** {'\u2705 Scheduled' if cand_val.get('interview_scheduled') else '\u2014'}")

                # Count emails
                num_emails = len(cand_val.get("emails_sent", []))
                sent_count = sum(1 for e in cand_val.get("emails_sent", []) if e.get("send_status") == "SENT")
                st.markdown(f"**Emails:** {num_emails} total, {sent_count} sent")

                if st.button(f"Load {cand_val['name']}", key=f"load_{cid_key}"):
                    st.session_state.current_candidate_id = cid_key
                    st.success(f"Loaded {cand_val['name']} as active candidate.")
                    st.rerun()

# ─────────────────────────────────────────────
# FOOTER
# ─────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("\U0001f916 *AI Recruitment Screening Agent*")
st.sidebar.markdown("Built for fair, explainable, and compliant hiring.")
st.sidebar.markdown("*\u26a1 With automated email pipeline*")
