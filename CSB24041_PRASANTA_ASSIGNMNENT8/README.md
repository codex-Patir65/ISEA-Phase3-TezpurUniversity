# Assignment 8 — Running the Experiments

These are the exact steps to generate the **real** data the assignment requires
(performance_results.csv, graphs/, screenshots/, Wireshark captures). Nothing in
`report.docx` for Sections 11–13 will be genuine until you complete these steps.

## 0. Setup
```bash
pip3 install psutil matplotlib
```
Copy `server.py`, `client_gui.py`, `config.json`, `make_users.py`,
`load_test_client.py`, `generate_graphs.py` into your project folder
(same one as your Assignment 7 GitHub repo).

On the server host, create test accounts once:
```bash
python3 make_users.py
```

## 1. Start Mininet
```bash
sudo mn --topo single,11
```
This gives you 1 switch and 11 hosts (h1–h11): use h1 as the server, h2–h11 as
up to 10 clients.

Inside the Mininet CLI, open terminals on the hosts you need, e.g.:
```
mininet> xterm h1 h2 h3
```

## 2. Baseline ("before") run — original Assignment 7 code
On **h1** (server host), run your *original, unmodified* Assignment 7 `server.py`.

On **h2** (or another client host), run the load generator against it:
```bash
python3 load_test_client.py --server 10.0.0.1 --clients 5  --duration 30
python3 load_test_client.py --server 10.0.0.1 --clients 8  --duration 30
python3 load_test_client.py --server 10.0.0.1 --clients 10 --duration 30
```
Stop the baseline server, then rename the CSV it produced:
```bash
cp performance_results.csv performance_results_before.csv
```

## 3. Optimized ("after") run — this assignment's server.py
On **h1**, start the optimized server:
```bash
python3 server.py
```
On a client host, repeat the same three load-test runs:
```bash
python3 load_test_client.py --server 10.0.0.1 --clients 5  --duration 30
python3 load_test_client.py --server 10.0.0.1 --clients 8  --duration 30
python3 load_test_client.py --server 10.0.0.1 --clients 10 --duration 30
```
This time keep `performance_results.csv` as-is (it's a required deliverable)
and also copy it:
```bash
cp performance_results.csv performance_results_after.csv
```

While the 10-client run is going, also test **Task 1 & 2 manually**:
- Kill a client (`Ctrl+C` or `kill`) mid-conversation and confirm the server
  log shows it detected and removed within `client_idle_timeout_sec`.
- Kill the optimized server with `Ctrl+C` while clients are connected and
  confirm you see `[SHUTDOWN] ...` messages and connected GUI clients get a
  "Server Shutdown" popup.
- Kill and restart the server while a `client_gui.py` GUI client is running,
  and confirm the status label shows "Reconnecting..." and it rejoins
  automatically.

Take screenshots of each of these into `screenshots/`.

## 4. Generate graphs
```bash
python3 generate_graphs.py
```
This reads `performance_results_before.csv` and `performance_results_after.csv`
(or just `performance_results.csv` if you only have one) and writes PNGs into
`graphs/`. Insert these into Sections 11–12 of `report.docx`.

## 5. Wireshark capture (Task 6)
On the server host or switch interface:
```bash
sudo tcpdump -i any -w chat_capture.pcap port 5000
```
Run a short normal chat session (2–3 clients) while capturing, then open the
`.pcap` in Wireshark and record:
- The TCP three-way handshake (SYN, SYN-ACK, ACK) for a client connecting
- A few `PSH, ACK` packets carrying chat messages
- The FIN/ACK sequence when a client disconnects
Screenshot each and write 1–2 paragraphs per screenshot in Section 13.

## 6. GitHub (Task 7)
```bash
git add server.py client_gui.py config.json performance_results.csv graphs/ screenshots/ report.pdf handwritten_reflection.pdf
git commit -m "Assignment 8: optimization, scalability, reliability"
git push
```
Keep your existing repo name convention: `ISEAPhase3-TezpurUniversity-<YourName>`.
