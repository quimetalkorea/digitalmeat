# -*- coding: utf-8 -*-
"""
디지털미트 모니터링 컨트롤 패널
- monitor.py / sales_monitor.py 시작·중지 버튼
- 백필·병합·즉시대조 원클릭 실행
- 두 모니터의 로그를 한 화면에 표시

실행: python control_panel.py
(바탕화면 바로가기: control_panel.py 우클릭 → 보내기 → 바탕화면)
"""

import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext
from datetime import datetime

PANEL_VERSION = "v1.4"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# (표시 이름, 파일명, 태그색)
DAEMONS = [
    ("구매 모니터 (시세 매칭·문의)", "monitor.py", "#2e7d32"),
    ("판매↔구매 크로스 매칭", "sales_monitor.py", "#1565c0"),
]

FILES_TO_OPEN = [
    ("모니터 로그", "monitor_log.txt"),
    ("크로스 로그", "sales_monitor_log.txt"),
    ("매칭 짝 CSV", "matched_pairs.csv"),
    ("연락처", "contacts.csv"),
    ("연락처 후보", "contacts_candidates.csv"),
]


class Panel:
    def __init__(self, root):
        self.root = root
        root.title(f"디지털미트 모니터링 컨트롤 패널  {PANEL_VERSION}")
        root.geometry("880x620")
        self.procs = {}          # script -> Popen
        self.buttons = {}        # script -> (버튼, 상태라벨)
        self.log_q = queue.Queue()

        # ── 최상단: 전체 제어 ──
        ctrl = tk.Frame(root)
        ctrl.pack(fill="x", padx=10, pady=(10, 0))
        tk.Button(ctrl, text="모두 시작", width=10,
                  command=self.start_all).pack(side="left", padx=(0, 4))
        tk.Button(ctrl, text="모두 중지", width=10,
                  command=self.stop_all).pack(side="left", padx=4)
        tk.Button(ctrl, text="패널 종료", width=10, bg="#c62828", fg="white",
                  activebackground="#e53935", activeforeground="white",
                  command=self.on_close).pack(side="right")

        # ── 상단: 상시 모니터 ──
        top = tk.LabelFrame(root, text=" 상시 모니터 ", padx=8, pady=6)
        top.pack(fill="x", padx=10, pady=(6, 4))
        for name, script, color in DAEMONS:
            row = tk.Frame(top)
            row.pack(fill="x", pady=3)
            status = tk.Label(row, text="●", fg="#999", font=("Arial", 14))
            status.pack(side="left")
            tk.Label(row, text=name, width=28, anchor="w").pack(side="left", padx=4)
            btn = tk.Button(row, text="시작", width=8,
                            command=lambda s=script: self.toggle(s))
            btn.pack(side="left", padx=4)
            self.buttons[script] = (btn, status, color)

        # ── 중단: 일회성 작업 ──
        mid = tk.LabelFrame(root, text=" 일회성 작업 ", padx=8, pady=6)
        mid.pack(fill="x", padx=10, pady=4)
        row1 = tk.Frame(mid)
        row1.pack(fill="x", pady=2)
        tk.Button(row1, text="판매글 백필", width=12,
                  command=self.run_backfill).pack(side="left", padx=3)
        tk.Label(row1, text="페이지:").pack(side="left")
        self.pages_var = tk.StringVar(value="50")
        tk.Entry(row1, textvariable=self.pages_var, width=5).pack(side="left", padx=(0, 12))
        tk.Button(row1, text="병합 (merge)", width=12,
                  command=lambda: self.run_once("merge_sell.py")).pack(side="left", padx=3)
        tk.Button(row1, text="즉시 대조", width=10,
                  command=lambda: self.run_once("cross_check.py")).pack(side="left", padx=3)
        tk.Button(row1, text="본문 수집", width=10,
                  command=self.run_enrich).pack(side="left", padx=3)
        tk.Label(row1, text="건수:").pack(side="left")
        self.enrich_var = tk.StringVar(value="50")
        tk.Entry(row1, textvariable=self.enrich_var, width=5).pack(side="left", padx=(0, 8))
        tk.Button(row1, text="연락처 수확", width=10,
                  command=lambda: self.run_once("harvest_contacts.py")).pack(side="left", padx=3)

        # ── 파일 바로가기 ──
        row2 = tk.Frame(mid)
        row2.pack(fill="x", pady=2)
        tk.Label(row2, text="열기:").pack(side="left")
        for label, fname in FILES_TO_OPEN:
            tk.Button(row2, text=label,
                      command=lambda f=fname: self.open_file(f)).pack(side="left", padx=3)

        # ── 하단: 로그(좌) + 문의 문구(우) ──
        bottom = tk.Frame(root)
        bottom.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        logf = tk.LabelFrame(bottom, text=" 로그 ", padx=4, pady=4)
        logf.pack(side="left", fill="both", expand=True)
        self.log = scrolledtext.ScrolledText(logf, state="disabled", height=20,
                                             font=("Consolas", 9), bg="#111", fg="#ddd")
        self.log.pack(fill="both", expand=True)

        inqf = tk.LabelFrame(bottom, text=" 문의 문구 (더블클릭=복사) ", padx=4, pady=4)
        inqf.pack(side="left", fill="y", padx=(6, 0))
        self.inq_list = tk.Listbox(inqf, width=34, font=("맑은 고딕", 9))
        self.inq_list.pack(fill="both", expand=True)
        self.inq_list.bind("<Double-Button-1>", self.copy_inquiry)
        btnrow = tk.Frame(inqf)
        btnrow.pack(fill="x", pady=(4, 0))
        tk.Button(btnrow, text="선택 복사", command=self.copy_inquiry).pack(side="left", padx=2)
        tk.Button(btnrow, text="지난 문의 불러오기", command=self.load_past_inquiries).pack(side="left", padx=2)
        self.inquiries = []          # [(라벨, 문구)]
        self._pending_supplier = ""
        for _, script, color in DAEMONS:
            self.log.tag_config(script, foreground=color)
        self.log.tag_config("panel", foreground="#e6a817")

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll_logs()
        self.append("panel", f"컨트롤 패널 {PANEL_VERSION} 준비 완료. 모니터를 시작하세요.")

    # ── 프로세스 관리 ──
    def start_all(self):
        for _, script, _ in DAEMONS:
            if not (script in self.procs and self.procs[script].poll() is None):
                self.start(script)

    def stop_all(self):
        for _, script, _ in DAEMONS:
            self.stop(script)

    def toggle(self, script):
        if script in self.procs and self.procs[script].poll() is None:
            self.stop(script)
        else:
            self.start(script)

    def start(self, script, extra_args=None, daemon=True):
        path = os.path.join(BASE_DIR, script)
        if not os.path.exists(path):
            messagebox.showerror("파일 없음", f"{script} 가 {BASE_DIR} 에 없습니다.")
            return None
        args = [PY, "-u", path] + (extra_args or [])
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        # 자식 파이썬이 한글을 UTF-8로 출력하게 강제 (파이프 실행 시 CP949 깨짐 방지)
        env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
        try:
            p = subprocess.Popen(
                args, cwd=BASE_DIR, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True, encoding="utf-8", errors="replace",
                creationflags=flags,
            )
        except Exception as e:
            messagebox.showerror("실행 실패", f"{script}: {e}")
            return None
        if daemon:
            self.procs[script] = p
            self.set_running(script, True)
        threading.Thread(target=self.reader, args=(script, p, daemon), daemon=True).start()
        self.append("panel", f"{script} 시작 (PID {p.pid})")
        return p

    def stop(self, script):
        p = self.procs.get(script)
        if p and p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
            self.append("panel", f"{script} 중지")
        self.set_running(script, False)

    def reader(self, script, p, daemon):
        for line in iter(p.stdout.readline, ""):
            self.log_q.put((script, line.rstrip("\n")))
        p.stdout.close()
        rc = p.wait()
        self.log_q.put(("panel", f"{script} 종료 (코드 {rc})"))
        if daemon:
            self.log_q.put(("__ended__", script))

    def run_once(self, script, extra_args=None):
        self.start(script, extra_args=extra_args, daemon=False)

    def run_enrich(self):
        n = self.enrich_var.get().strip() or "50"
        if not n.isdigit():
            messagebox.showwarning("입력 확인", "건수는 숫자로 입력하세요.")
            return
        self.run_once("enrich_sell.py", extra_args=[n])

    def run_backfill(self):
        pages = self.pages_var.get().strip() or "50"
        if not pages.isdigit():
            messagebox.showwarning("입력 확인", "페이지 수는 숫자로 입력하세요.")
            return
        self.run_once("backfill_sell.py", extra_args=[pages])

    # ── UI 갱신 ──
    def set_running(self, script, running):
        if script not in self.buttons:
            return
        btn, status, color = self.buttons[script]
        if running:
            btn.config(text="중지")
            status.config(fg=color)
        else:
            btn.config(text="시작")
            status.config(fg="#999")

    def append(self, tag, text):
        self.log_q.put((tag, text))

    def poll_logs(self):
        try:
            while True:
                tag, line = self.log_q.get_nowait()
                if tag == "__ended__":
                    self.set_running(line, False)
                    continue
                self.capture_inquiry(line)
                prefix = {"monitor.py": "[monitor]", "sales_monitor.py": "[sales]  ",
                          "panel": "[panel]  "}.get(tag, f"[{tag}]")
                self.log.config(state="normal")
                self.log.insert("end", f"{datetime.now().strftime('%H:%M:%S')} {prefix} {line}\n",
                                tag if tag in ("monitor.py", "sales_monitor.py", "panel") else None)
                # 로그 5000줄 초과 시 앞부분 정리
                if float(self.log.index("end-1c").split(".")[0]) > 5000:
                    self.log.delete("1.0", "1000.0")
                self.log.see("end")
                self.log.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(200, self.poll_logs)

    def capture_inquiry(self, line):
        """모니터 로그에서 '[N] 거래처...' + '문구: ...' 를 잡아 목록에 추가."""
        s = line.strip()
        m = re.match(r"\[\d+\]\s+(.+?)\s+/\s+(.+?)\s+/", s)
        if m:
            self._pending_supplier = f"{m.group(1)} ({m.group(2)})"
            return
        if s.startswith("문구:"):
            text = s[len("문구:"):].strip()
            if not text:
                return
            label = self._pending_supplier or text[:26]
            stamp = datetime.now().strftime("%H:%M")
            self.inquiries.insert(0, (f"{stamp} {label}", text))
            self.inquiries = self.inquiries[:60]
            self.refresh_inq_list()
            self._pending_supplier = ""

    def refresh_inq_list(self):
        self.inq_list.delete(0, "end")
        for lbl, _ in self.inquiries:
            self.inq_list.insert("end", lbl)

    def load_past_inquiries(self, silent=False):
        """monitor_log.txt에서 과거 문의 문구를 읽어 목록에 채움."""
        path = os.path.join(BASE_DIR, "monitor_log.txt")
        if not os.path.exists(path):
            if not silent:
                messagebox.showinfo("로그 없음", "monitor_log.txt 가 아직 없습니다.")
            return
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                lines = f.read().splitlines()
        except Exception as e:
            if not silent:
                messagebox.showerror("읽기 실패", str(e))
            return
        entries = []
        i = 0
        while i < len(lines):
            s = lines[i].strip()
            if s.startswith("문의)"):
                header = s[len("문의)"):].strip()
                parts = [p.strip() for p in header.split("/")]
                label = parts[0] + (f" ({parts[1]})" if len(parts) > 1 else "")
                text = lines[i + 1].strip() if i + 1 < len(lines) else ""
                if text:
                    entries.append((label, text))
                i += 2
            else:
                i += 1
        if not entries:
            if not silent:
                messagebox.showinfo("문의 없음", "로그에 저장된 문의 문구가 없습니다.")
            return
        past = entries[-30:][::-1]  # 최신이 위로
        # 현재 세션에서 잡은 것과 합치되 중복 문구 제거
        existing_texts = {t for _, t in self.inquiries}
        for lbl, t in past:
            if t not in existing_texts:
                self.inquiries.append((f"(지난) {lbl}", t))
        self.inquiries = self.inquiries[:60]
        self.refresh_inq_list()
        self.append("panel", f"지난 문의 {len(past)}건 불러옴 (더블클릭=복사)")

    def copy_inquiry(self, event=None):
        sel = self.inq_list.curselection()
        if not sel:
            return
        label, text = self.inquiries[sel[0]]
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.append("panel", f"📋 문구 복사됨 → {label} (카톡에 Ctrl+V)")

    def open_file(self, fname):
        path = os.path.join(BASE_DIR, fname)
        if not os.path.exists(path):
            messagebox.showinfo("파일 없음", f"{fname} 이 아직 생성되지 않았습니다.")
            return
        try:
            os.startfile(path)  # Windows
        except AttributeError:
            subprocess.Popen(["xdg-open", path])

    def on_close(self):
        running = [s for s, p in self.procs.items() if p.poll() is None]
        if running:
            if not messagebox.askyesno("종료 확인",
                    f"실행 중인 모니터 {len(running)}개를 중지하고 닫을까요?\n({', '.join(running)})"):
                return
            for s in running:
                self.stop(s)
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    Panel(root)
    root.mainloop()