import requests, base64, json

H = {"X-API-Key": "jobboerse-jobsuche",
     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128"}
B = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"

r = requests.get(B + "/pc/v6/jobs", params={"was": "Data Analyst", "size": 3, "angebotsart": 1}, headers=H, timeout=30)
d = r.json()
print("top-level keys:", sorted(d.keys()))
jobs = d.get("ergebnisliste") or []
print("jobs returned:", len(jobs), "| total:", d.get("maxErgebnisse"))
j = jobs[0]
print("job fields:", sorted(j.keys()))
print(json.dumps(j, ensure_ascii=False, indent=1)[:1500])

ref = j.get("referenznummer") or j.get("refnr") or j.get("hashId")
print("\nrefnr:", ref)
for path in ("/pc/v4/jobdetails/", "/pc/v3/jobdetails/", "/pc/v6/jobdetails/"):
    rd = requests.get(B + path + base64.b64encode(ref.encode()).decode(), headers=H, timeout=30)
    print(path, "->", rd.status_code)
    if rd.status_code == 200:
        dd = rd.json()
        print("detail fields:", sorted(dd.keys()))
        for k in sorted(dd.keys()):
            v = json.dumps(dd[k], ensure_ascii=False)
            if any(s in (k + v).lower() for s in ("mail", "kontakt", "ansprech", "bewerb", "adresse", "url")):
                print(" ", k, "=", v[:400])
        break