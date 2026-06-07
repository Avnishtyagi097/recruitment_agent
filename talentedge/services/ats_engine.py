import re

SKILLS = {
    "Programming": ["python","java","javascript","typescript","scala","r","go","rust","c++","c#","ruby","kotlin","bash","shell"],
    "Databases": ["sql","mysql","postgresql","mongodb","cassandra","redis","dynamodb","oracle","snowflake","redshift","bigquery","hive","elasticsearch"],
    "Cloud": ["aws","azure","gcp","google cloud","s3","ec2","lambda","iam","cloudformation","sagemaker","emr","glue","athena","kinesis"],
    "Big Data": ["spark","pyspark","hadoop","kafka","flink","databricks","delta lake","presto","trino","iceberg"],
    "ETL": ["etl","elt","airflow","dbt","nifi","talend","informatica","dagster","prefect","data pipeline","pipeline"],
    "DevOps": ["docker","kubernetes","terraform","ansible","jenkins","github actions","gitlab ci","helm","prometheus","grafana","datadog","elk"],
    "Data": ["data modeling","data warehouse","data lake","data governance","data quality","data catalog","star schema","snowflake schema","data vault","data lineage","medallion"],
    "BI": ["tableau","power bi","looker","matplotlib","seaborn","plotly","superset"],
    "ML": ["machine learning","deep learning","tensorflow","pytorch","scikit-learn","nlp","computer vision","mlops"],
    "SE": ["git","agile","scrum","rest api","graphql","microservices","ci/cd","tdd","unit testing","design patterns","jwt","oauth"],
    "Certs": ["databricks certified","aws certified","google professional","azure certified","ckad","cka","terraform associate"],
}


def extract_skills(text: str) -> dict:
    tl = text.lower()
    found = {}
    for cat, skills in SKILLS.items():
        matched = []
        for s in skills:
            if len(s) <= 3:
                if re.search(r'\b' + re.escape(s) + r'\b', tl):
                    matched.append(s)
            else:
                if s in tl:
                    matched.append(s)
        if matched:
            found[cat] = list(set(matched))
    return found


def extract_experience(text: str) -> int:
    patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|exp)',
        r'(?:experience)\s*(?:of)?\s*(\d+)\+?\s*(?:years?|yrs?)',
        r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:in|of|working)',
    ]
    years = []
    for p in patterns:
        for m in re.findall(p, text.lower()):
            try:
                y = int(m)
                if 0 < y < 50:
                    years.append(y)
            except:
                pass
    return max(years) if years else 0


def extract_education(text: str) -> list:
    kw = ["bachelor","master","phd","b.tech","m.tech","bsc","msc","mba",
          "computer science","data science","engineering","university","degree"]
    return [k for k in kw if k in text.lower()]


def calculate_ats_score(cv_text: str, jd_text: str) -> dict:
    if not cv_text:
        return {"ats_score": 0, "decision": "FAIL", "reasoning": "CV could not be parsed.",
                "matched_skills": [], "missing_skills": [], "experience_match": "",
                "strengths": [], "gaps": ["CV parsing failed"], "requires_review": True,
                "breakdown": {"skills":0,"experience":0,"education":0,"certifications":0,"tools":0}}

    cv_skills = extract_skills(cv_text)
    jd_skills = extract_skills(jd_text)
    cv_exp = extract_experience(cv_text)
    jd_exp = extract_experience(jd_text)
    cv_edu = extract_education(cv_text)
    jd_edu = extract_education(jd_text)

    cv_set = set()
    for s in cv_skills.values(): cv_set.update(s)
    jd_set = set()
    for s in jd_skills.values(): jd_set.update(s)

    # Skills 40%
    if jd_set:
        matched = cv_set & jd_set
        missing = jd_set - cv_set
        skill_pct = len(matched) / len(jd_set)
    else:
        matched, missing = cv_set, set()
        skill_pct = 0.5
    skill_score = min(skill_pct * 100, 100) * 0.40

    # Experience 20%
    if jd_exp > 0:
        if cv_exp >= jd_exp:
            exp_score = 100 * 0.20
            exp_match = f"CV: {cv_exp} yrs >= JD: {jd_exp} yrs"
        elif cv_exp >= jd_exp * 0.7:
            exp_score = 75 * 0.20
            exp_match = f"CV: {cv_exp} yrs (close to JD: {jd_exp} yrs)"
        else:
            exp_score = max(30, (cv_exp / jd_exp) * 100) * 0.20
            exp_match = f"CV: {cv_exp} yrs < JD: {jd_exp} yrs"
    else:
        exp_score = 60 * 0.20
        exp_match = f"CV: {cv_exp} yrs (JD not specified)"

    # Education 15%
    edu_pct = len(set(cv_edu) & set(jd_edu)) / len(set(jd_edu)) if jd_edu else 0.6
    edu_score = min(edu_pct * 100, 100) * 0.15

    # Certs 10%
    cv_c = cv_skills.get("Certs", [])
    jd_c = jd_skills.get("Certs", [])
    cert_pct = len(set(cv_c) & set(jd_c)) / len(set(jd_c)) if jd_c else (0.5 if cv_c else 0.3)
    cert_score = min(cert_pct * 100, 100) * 0.10

    # Tools 15%
    tm = tt = 0
    for cat in ["Cloud", "Big Data", "DevOps", "BI"]:
        jt = set(jd_skills.get(cat, []))
        ct = set(cv_skills.get(cat, []))
        tt += len(jt); tm += len(ct & jt)
    tool_pct = (tm / tt) if tt > 0 else 0.5
    tool_score = min(tool_pct * 100, 100) * 0.15

    total = round(skill_score + exp_score + edu_score + cert_score + tool_score, 1)
    total = min(total, 100)

    strengths, gaps = [], []
    if jd_set and skill_pct > 0.7: strengths.append(f"Strong skill match ({len(matched)}/{len(jd_set)})")
    elif jd_set: gaps.append(f"Missing {len(missing)} of {len(jd_set)} skills")
    if cv_exp >= jd_exp and jd_exp > 0: strengths.append(f"Meets experience ({cv_exp} yrs)")
    elif jd_exp > 0: gaps.append(f"Experience gap ({cv_exp} vs {jd_exp} yrs)")

    decision = "PASS" if total > 85 else "FAIL"
    requires_review = 75 <= total <= 85

    return {
        "ats_score": total, "decision": decision,
        "reasoning": f"Score: {total}/100. Skills: {len(matched)}/{len(jd_set)}. Experience: {exp_match}.",
        "matched_skills": sorted(list(matched)), "missing_skills": sorted(list(missing)),
        "experience_match": exp_match, "strengths": strengths, "gaps": gaps,
        "requires_review": requires_review,
        "breakdown": {
            "skills": round(skill_score, 1), "experience": round(exp_score, 1),
            "education": round(edu_score, 1), "certifications": round(cert_score, 1),
            "tools": round(tool_score, 1),
        },
    }
