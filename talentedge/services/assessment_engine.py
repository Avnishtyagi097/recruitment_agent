import random

QUESTION_BANKS = {
"Data Engineer": [
  {"q":"What does ETL stand for?","options":["Extract, Transform, Load","Execute, Transfer, Log","Extract, Transfer, Load","Execute, Transform, Load"],"answer":0,"topic":"ETL","difficulty":"easy"},
  {"q":"Which SQL clause filters groups?","options":["WHERE","HAVING","GROUP BY","ORDER BY"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"Star schema fact tables connect to:","options":["Other facts","Dimension tables","Staging","Logs"],"answer":1,"topic":"Modeling","difficulty":"easy"},
  {"q":"Spark component for structured data?","options":["Streaming","MLlib","Spark SQL","GraphX"],"answer":2,"topic":"Spark","difficulty":"easy"},
  {"q":"Primary purpose of Apache Airflow?","options":["Storage","Workflow orchestration","Streaming","ML"],"answer":1,"topic":"Orchestration","difficulty":"easy"},
  {"q":"Most used Python data manipulation lib?","options":["NumPy","Matplotlib","Pandas","Sklearn"],"answer":2,"topic":"Python","difficulty":"easy"},
  {"q":"What is a slowly changing dimension?","options":["Never changes","Tracks changes over time","Real-time only","Temporary"],"answer":1,"topic":"Warehousing","difficulty":"medium"},
  {"q":"Batch vs stream processing?","options":["Batch=realtime","Batch=chunks, stream=continuous","Same thing","Batch faster"],"answer":1,"topic":"Processing","difficulty":"easy"},
  {"q":"Columnar storage format?","options":["CSV","JSON","Parquet","XML"],"answer":2,"topic":"Storage","difficulty":"easy"},
  {"q":"ACID Isolation guarantees?","options":["Permanent save","No interference","All or none","Valid data"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"What is a Spark DataFrame?","options":["Key-value pairs","Named columns collection","Python dict","Unschema RDD"],"answer":1,"topic":"Spark","difficulty":"easy"},
  {"q":"Range partitioning splits by?","options":["Hash","Date/range","Round-robin","Random"],"answer":1,"topic":"Performance","difficulty":"medium"},
  {"q":"Purpose of a data catalog?","options":["Store data","Metadata & discovery","Run ETL","Monitor"],"answer":1,"topic":"Governance","difficulty":"easy"},
  {"q":"AWS serverless data warehouse?","options":["RDS","DynamoDB","Redshift Serverless","S3"],"answer":2,"topic":"Cloud","difficulty":"medium"},
  {"q":"Schema-on-read means?","options":["Write-time schema","Read-time schema","No schema","Separate DB"],"answer":1,"topic":"Modeling","difficulty":"medium"},
  {"q":"Kafka topic is?","options":["Consumer group","Category for records","Broker type","Serialization"],"answer":1,"topic":"Streaming","difficulty":"easy"},
  {"q":"SQL window function does?","options":["Filters before agg","Calc across related rows","Joins tables","Creates table"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"dbt is used for?","options":["MapReduce","Data transformation","Legacy ETL","File transfer"],"answer":1,"topic":"ETL","difficulty":"medium"},
  {"q":"Data lineage tracks?","options":["Transfer speed","Origin & transformations","Dataset size","Encryption"],"answer":1,"topic":"Governance","difficulty":"easy"},
  {"q":"Delta table in Databricks?","options":["Temp view","ACID on Parquet","CSV file","Stream only"],"answer":1,"topic":"Databricks","difficulty":"medium"},
  {"q":"FULL OUTER JOIN returns?","options":["Matching only","Left+matching","All from both","Cartesian"],"answer":2,"topic":"SQL","difficulty":"easy"},
  {"q":"Idempotent pipeline means?","options":["Runs once","Same result on rerun","Faster","No input"],"answer":1,"topic":"ETL","difficulty":"medium"},
  {"q":"Spark action that triggers compute?","options":["map()","filter()","collect()","flatMap()"],"answer":2,"topic":"Spark","difficulty":"medium"},
  {"q":"CAP theorem is about?","options":["Modeling","Consistency+Availability+Partition","Caching","Compression"],"answer":1,"topic":"Distributed","difficulty":"medium"},
  {"q":"Python ORM library?","options":["requests","sqlalchemy","flask","beautifulsoup"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"Materialized view is?","options":["Virtual table","Stored query result","Temp table","Index"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"Azure big data service?","options":["Blob Storage","Synapse Analytics","Functions","DevOps"],"answer":1,"topic":"Cloud","difficulty":"medium"},
  {"q":"Data skew means?","options":["Uniform distribution","Uneven partition distribution","Corruption","Sorting"],"answer":1,"topic":"Performance","difficulty":"medium"},
  {"q":"Schema registry in streaming?","options":["Permanent storage","Schema management","Message routing","Lag monitor"],"answer":1,"topic":"Streaming","difficulty":"medium"},
  {"q":"DAG-based orchestration?","options":["Linear","Directed Acyclic Graph","Circular","Ad-hoc"],"answer":1,"topic":"Orchestration","difficulty":"easy"},
],
"Software Engineer": [
  {"q":"Binary search time complexity?","options":["O(n)","O(log n)","O(n log n)","O(1)"],"answer":1,"topic":"Algorithms","difficulty":"easy"},
  {"q":"Idempotent HTTP method?","options":["POST","PATCH","PUT","None"],"answer":2,"topic":"APIs","difficulty":"easy"},
  {"q":"SOLID S stands for?","options":["Single Responsibility","Separation","Singleton","Security"],"answer":0,"topic":"Design","difficulty":"easy"},
  {"q":"API Gateway is?","options":["Database","Single entry point","Test tool","Deploy server"],"answer":1,"topic":"Microservices","difficulty":"easy"},
  {"q":"FIFO data structure?","options":["Stack","Queue","Tree","Graph"],"answer":1,"topic":"DS","difficulty":"easy"},
  {"q":"Docker provides?","options":["Hardware virtualization","OS-level isolation","Compiler optimization","DB management"],"answer":1,"topic":"Docker","difficulty":"easy"},
  {"q":"Load balancer purpose?","options":["Store data","Distribute traffic","Compile code","Manage DB"],"answer":1,"topic":"System Design","difficulty":"easy"},
  {"q":"Unit testing verifies?","options":["Integration","Individual components","System","Acceptance"],"answer":1,"topic":"Testing","difficulty":"easy"},
  {"q":"What is a deadlock?","options":["Fast path","Processes waiting forever","Exception","Memory leak"],"answer":1,"topic":"Concurrency","difficulty":"medium"},
  {"q":"Git rebase does?","options":["Delete branch","Re-apply commits on new base","Merge repos","Create tag"],"answer":1,"topic":"Git","difficulty":"medium"},
  {"q":"CAP theorem applies to?","options":["UI","Distributed systems","Compilers","Sorting"],"answer":1,"topic":"System Design","difficulty":"medium"},
  {"q":"Singleton pattern ensures?","options":["Factory","Observer","One instance","Strategy"],"answer":2,"topic":"Patterns","difficulty":"easy"},
  {"q":"ORM purpose?","options":["Rendering","Map objects to DB","OS management","Routing"],"answer":1,"topic":"Databases","difficulty":"easy"},
  {"q":"HTTP 201 means?","options":["OK","Created","No Content","Redirect"],"answer":1,"topic":"APIs","difficulty":"easy"},
  {"q":"CI/CD stands for?","options":["Code Inspection","Continuous Integration/Delivery","Central Index","Compiled Instructions"],"answer":1,"topic":"DevOps","difficulty":"easy"},
  {"q":"K8s Deployment manages?","options":["StatefulSet","Stateless apps","DaemonSet","Job"],"answer":1,"topic":"K8s","difficulty":"medium"},
  {"q":"Race condition is?","options":["Benchmark","Timing-dependent output","Protocol","Sort type"],"answer":1,"topic":"Concurrency","difficulty":"medium"},
  {"q":"DRY stands for?","options":["Don't Repeat Yourself","Data Replication","Dynamic Resource","Deploy Run"],"answer":0,"topic":"Design","difficulty":"easy"},
  {"q":"GraphQL uses which protocol?","options":["FTP","HTTP","SMTP","SSH"],"answer":1,"topic":"APIs","difficulty":"easy"},
  {"q":"Hash table avg lookup?","options":["O(n)","O(log n)","O(1)","O(n^2)"],"answer":2,"topic":"DS","difficulty":"easy"},
  {"q":"Blue-green deployment?","options":["Testing","Two identical envs, zero-downtime","Color coding","Branching"],"answer":1,"topic":"DevOps","difficulty":"medium"},
  {"q":"Dependency injection?","options":["Injecting bugs","External dependency provision","SQL injection","Protocol"],"answer":1,"topic":"Patterns","difficulty":"medium"},
  {"q":"Database index purpose?","options":["Backup","Speed up retrieval","Encrypt","Compress"],"answer":1,"topic":"Databases","difficulty":"easy"},
  {"q":"Sprint retrospective is?","options":["Planning","Reflect on improvements","Demo","Standup"],"answer":1,"topic":"Agile","difficulty":"easy"},
  {"q":"JWT token used for?","options":["Storage","Stateless auth","Compression","Compilation"],"answer":1,"topic":"Security","difficulty":"easy"},
  {"q":"WebSocket is for?","options":["Static files","Full-duplex realtime","Email","DB queries"],"answer":1,"topic":"Networking","difficulty":"medium"},
  {"q":"Write-through cache?","options":["Cache-aside","Write cache+DB simultaneously","Write-back","Read-through"],"answer":1,"topic":"System Design","difficulty":"medium"},
  {"q":"TDD means?","options":["Test after deploy","Write tests first","Manual only","No testing"],"answer":1,"topic":"Testing","difficulty":"easy"},
  {"q":"Reverse proxy?","options":["Blocks traffic","Forwards to backend","VPN","Firewall"],"answer":1,"topic":"Networking","difficulty":"medium"},
  {"q":"Docker Compose purpose?","options":["Build images","Multi-container apps","Monitor","Deploy K8s"],"answer":1,"topic":"Docker","difficulty":"medium"},
],
"Data Analyst": [
  {"q":"SQL GROUP BY does?","options":["Sorts","Groups for aggregation","Filters","Joins"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"Best chart for proportions?","options":["Line","Pie","Scatter","Histogram"],"answer":1,"topic":"Viz","difficulty":"easy"},
  {"q":"Excel lookup function?","options":["SUM","VLOOKUP","COUNT","IF"],"answer":1,"topic":"Excel","difficulty":"easy"},
  {"q":"p-value in statistics?","options":["Probability assuming null","Mean","Correlation","Std dev"],"answer":0,"topic":"Stats","difficulty":"medium"},
  {"q":"Python viz library?","options":["Pandas","Matplotlib","SQLAlchemy","Flask"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"KPI stands for?","options":["Key Performance Indicator","Key Python Interface","Kernel Processing","Knowledge Pattern"],"answer":0,"topic":"Business","difficulty":"easy"},
  {"q":"LEFT JOIN returns?","options":["Matching only","All left + matching right","All right","Cartesian"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"Mean vs median?","options":["Same","Mean=average, median=middle","Mean=mode","Median=average"],"answer":1,"topic":"Stats","difficulty":"easy"},
  {"q":"Tableau calculated field?","options":["Pre-built","Custom formula field","CSV column","Filter"],"answer":1,"topic":"BI","difficulty":"easy"},
  {"q":"Data normalization?","options":["Delete dupes","Scale to standard range","Backup","Encrypt"],"answer":1,"topic":"Cleaning","difficulty":"easy"},
  {"q":"COUNT() counts?","options":["SUM values","Non-NULL values","AVG","MAX"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"Correlation coefficient measures?","options":["Data size","Linear relationship","Sorting","Data type"],"answer":1,"topic":"Stats","difficulty":"medium"},
  {"q":"Pivot table used for?","options":["Encryption","Summarizing data","Macros","Charts only"],"answer":1,"topic":"Excel","difficulty":"easy"},
  {"q":"Power BI DAX is?","options":["Data Analysis Expressions","Database XML","Dynamic App","Data Archive"],"answer":0,"topic":"BI","difficulty":"medium"},
  {"q":"Data profiling examines?","options":["Visualization","Quality & structure","Deletion","Encryption"],"answer":1,"topic":"Cleaning","difficulty":"easy"},
  {"q":"Outlier is?","options":["Common point","Significantly different point","Missing value","Duplicate"],"answer":1,"topic":"Stats","difficulty":"easy"},
  {"q":"Pandas read CSV?","options":["pd.open_csv()","pd.read_csv()","pd.load_csv()","pd.import_csv()"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"A/B testing?","options":["Debugging","Compare two versions","Storage format","Viz type"],"answer":1,"topic":"Stats","difficulty":"medium"},
  {"q":"SQL subquery?","options":["Backup query","Nested query","Delete op","Schema def"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"Box plot shows?","options":["Trends","Quartiles & outliers","Proportions","Correlations"],"answer":1,"topic":"Viz","difficulty":"easy"},
  {"q":"DISTINCT keyword?","options":["Sort","Remove duplicates","Count","Group"],"answer":1,"topic":"SQL","difficulty":"easy"},
  {"q":"Regression analysis?","options":["Classification","Model dependent/independent vars","Clustering","Cleaning"],"answer":1,"topic":"Stats","difficulty":"medium"},
  {"q":"Trend chart type?","options":["Pie","Bar","Line","Treemap"],"answer":2,"topic":"Viz","difficulty":"easy"},
  {"q":"Data wrangling?","options":["Deletion","Clean & transform raw data","Encryption","Visualization"],"answer":1,"topic":"Cleaning","difficulty":"easy"},
  {"q":"Mode in dataset?","options":["Average","Middle value","Most frequent","Range"],"answer":2,"topic":"Stats","difficulty":"easy"},
  {"q":"SQL COALESCE?","options":["Joins","First non-NULL","Sorts","Deletes NULLs"],"answer":1,"topic":"SQL","difficulty":"medium"},
  {"q":"Central Limit Theorem?","options":["Sample means -> normal dist","All normal","Variance=0","Mean=median"],"answer":0,"topic":"Stats","difficulty":"hard"},
  {"q":"Pandas groupby?","options":["Sorts","Groups for aggregation","Merges","Drops dupes"],"answer":1,"topic":"Python","difficulty":"easy"},
  {"q":"Standard deviation?","options":["Average","Spread around mean","Maximum","Range"],"answer":1,"topic":"Stats","difficulty":"easy"},
  {"q":"Cohort analysis?","options":["All users together","Group by shared characteristics","ML technique","DB design"],"answer":1,"topic":"Business","difficulty":"medium"},
],
"DevOps Engineer": [
  {"q":"IaC means?","options":["Code in infra","Infra via definition files","Language","Database"],"answer":1,"topic":"IaC","difficulty":"easy"},
  {"q":"Container orchestration tool?","options":["Docker","Kubernetes","Jenkins","Terraform"],"answer":1,"topic":"K8s","difficulty":"easy"},
  {"q":"CI stands for?","options":["Code Integration","Continuous Integration","Central Infra","Container Isolation"],"answer":1,"topic":"CI/CD","difficulty":"easy"},
  {"q":"Dockerfile is?","options":["Log file","Build instructions","K8s config","Dashboard"],"answer":1,"topic":"Docker","difficulty":"easy"},
  {"q":"Terraform used for?","options":["Monitoring","Infra provisioning","Testing","Container runtime"],"answer":1,"topic":"IaC","difficulty":"easy"},
  {"q":"K8s Pod is?","options":["Network policy","Smallest deployable unit","Storage volume","Node"],"answer":1,"topic":"K8s","difficulty":"easy"},
  {"q":"Prometheus monitors?","options":["Code quality","System metrics","Container images","Cost"],"answer":1,"topic":"Monitoring","difficulty":"easy"},
  {"q":"Helm chart is?","options":["Dashboard","K8s resource package","Docker image","CI pipeline"],"answer":1,"topic":"K8s","difficulty":"medium"},
  {"q":"GitOps means?","options":["Git storage only","Git as source of truth for deploys","Test framework","DB versioning"],"answer":1,"topic":"CI/CD","difficulty":"medium"},
  {"q":"Secrets management tool?","options":["GitHub","HashiCorp Vault","Docker Hub","Grafana"],"answer":1,"topic":"Security","difficulty":"medium"},
  {"q":"Rolling deployment?","options":["All at once","Gradually replace instances","Rollback","Staging only"],"answer":1,"topic":"CI/CD","difficulty":"medium"},
  {"q":"ELK stack?","options":["Elasticsearch,Logstash,Kibana","Envoy,Linux,K8s","Elastic,Lambda,Kafka","Endpoint,Load,Key"],"answer":0,"topic":"Monitoring","difficulty":"easy"},
  {"q":"chmod 755 means?","options":["Delete all","Owner:rwx,Group:r-x,Others:r-x","Read-only","Full access"],"answer":1,"topic":"Linux","difficulty":"medium"},
  {"q":"Canary deployment?","options":["All users","Small subset first","Rollback","Test env"],"answer":1,"topic":"CI/CD","difficulty":"medium"},
  {"q":"K8s ingress controller?","options":["Manage storage","External access to services","Monitor pods","Scale"],"answer":1,"topic":"K8s","difficulty":"medium"},
  {"q":"Ansible used for?","options":["Container orchestration","Config management","Compilation","DB management"],"answer":1,"topic":"IaC","difficulty":"easy"},
  {"q":"Blue-green deployment?","options":["Two envs, switch traffic","One server at a time","Testing","Branching"],"answer":0,"topic":"CI/CD","difficulty":"medium"},
  {"q":"K8s liveness probe?","options":["Ready for traffic","Container still running","CPU usage","Scale"],"answer":1,"topic":"K8s","difficulty":"medium"},
  {"q":"Shift left in DevOps?","options":["Move deploy earlier","Test+security earlier in lifecycle","Shift servers","Reduce team"],"answer":1,"topic":"CI/CD","difficulty":"easy"},
  {"q":"Least privilege principle?","options":["Admin for all","Minimum permissions needed","Disable all","One account"],"answer":1,"topic":"Security","difficulty":"easy"},
  {"q":"K8s DaemonSet?","options":["Deployment with replicas","Pod on all nodes","Service type","Config object"],"answer":1,"topic":"K8s","difficulty":"medium"},
  {"q":"Terraform state purpose?","options":["App logs","Track current infra state","Configure CI","Monitor"],"answer":1,"topic":"IaC","difficulty":"medium"},
  {"q":"Container registry?","options":["Runtime","Image repository","Monitoring","CI pipeline"],"answer":1,"topic":"Docker","difficulty":"easy"},
  {"q":"Chaos engineering?","options":["Random breaking","Deliberate failures for resilience","Debugging","Deploy strategy"],"answer":1,"topic":"SRE","difficulty":"medium"},
  {"q":"Grafana purpose?","options":["Code review","Metrics visualization","Container orchestration","CI/CD"],"answer":1,"topic":"Monitoring","difficulty":"easy"},
  {"q":"Multi-stage Docker build?","options":["Multiple containers","Multiple FROM to reduce size","Multiple envs","Multiple OS"],"answer":1,"topic":"Docker","difficulty":"medium"},
  {"q":"SRE stands for?","options":["Language","Software engineering for operations","Monitoring tool","Deploy strategy"],"answer":1,"topic":"SRE","difficulty":"easy"},
  {"q":"NAT gateway purpose?","options":["Route containers","Private subnet internet access","DNS records","Monitor traffic"],"answer":1,"topic":"Networking","difficulty":"medium"},
  {"q":"Immutable infrastructure?","options":["Changes frequently","Never modified, replaced instead","Temporary","No monitoring"],"answer":1,"topic":"IaC","difficulty":"medium"},
  {"q":"K8s ConfigMap?","options":["Store secrets","Non-confidential config key-values","Monitor pods","Manage deploys"],"answer":1,"topic":"K8s","difficulty":"medium"},
],
}


def get_questions(role: str, count: int = 30) -> list:
    role_key = None
    for k in QUESTION_BANKS:
        if k.lower() in role.lower() or role.lower() in k.lower():
            role_key = k
            break
    if not role_key:
        role_key = "Software Engineer"
    bank = QUESTION_BANKS[role_key][:]
    random.shuffle(bank)
    return bank[:count]


def score_assessment(questions: list, answers: dict) -> dict:
    if not questions:
        return {"score_percent": 0, "correct": 0, "total": 0, "decision": "FAIL",
                "strength_areas": [], "weak_areas": [], "topic_breakdown": {}}
    correct = 0
    topics = {}
    for i, q in enumerate(questions):
        t = q.get("topic", "General")
        if t not in topics:
            topics[t] = {"correct": 0, "total": 0}
        topics[t]["total"] += 1
        user_ans = answers.get(str(i))
        if user_ans is not None and int(user_ans) == q["answer"]:
            correct += 1
            topics[t]["correct"] += 1

    total = len(questions)
    score = round((correct / total) * 100, 1) if total > 0 else 0
    strong = [f"{t} ({d['correct']}/{d['total']})" for t, d in topics.items() if d["total"] > 0 and d["correct"]/d["total"] >= 0.75]
    weak = [f"{t} ({d['correct']}/{d['total']})" for t, d in topics.items() if d["total"] > 0 and d["correct"]/d["total"] < 0.5]
    decision = "PASS" if score > 90 else "FAIL"

    return {"score_percent": score, "correct": correct, "total": total, "decision": decision,
            "strength_areas": strong, "weak_areas": weak, "topic_breakdown": topics}
