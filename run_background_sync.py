# -*- coding: utf-8 -*-
import os
import sys
import time
import datetime
import traceback
import requests

REPO_DIR = r"C:\Users\oluca\painel-executivo-comercial"
LOG_FILE = os.path.join(REPO_DIR, "sync_daily.log")
PID_FILE = os.path.join(REPO_DIR, ".sync_daemon.pid")
INTERVAL_SECONDS = 7200  # Sincroniza a cada 2 horas enquanto o PC permanecer ligado

def log(msg):
    ts = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def is_another_instance_running():
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            old_pid = int(f.read().strip())
        if old_pid == os.getpid():
            return False
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x0400, False, old_pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True
    except Exception:
        pass
    return False

def write_pid():
    try:
        with open(PID_FILE, "w", encoding="utf-8") as f:
            f.write(str(os.getpid()))
    except Exception:
        pass

def wait_for_internet(timeout_seconds=90):
    log("Aguardando conexao com a internet apos inicializacao do Windows...")
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            r = requests.get("https://apps-chatwoot.r0ym2n.easypanel.host", timeout=5)
            if r.status_code in [200, 301, 302, 401, 403, 404]:
                log("Conexao com Chatwoot confirmada com sucesso!")
                return True
        except Exception:
            pass
        try:
            r = requests.get("https://1.1.1.1", timeout=5)
            if r.status_code in [200, 301, 302]:
                log("Conexao com a internet confirmada!")
                return True
        except Exception:
            pass
        time.sleep(5)
    log("Aviso: Timeout aguardando conexao com a internet. Tentando prosseguir...")
    return False

def execute_sync():
    log("Iniciando ciclo de sincronizacao comercial...")
    sys.path.insert(0, REPO_DIR)
    import sync_daily
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            sync_daily.sync()
            log("[SUCESSO] Sincronizacao concluida e enviada para o Vercel!")
            return True
        except Exception as e:
            err_msg = traceback.format_exc()
            log(f"[TENTATIVA {attempt}/{max_retries}] Erro durante sincronizacao: {e}")
            if attempt < max_retries:
                log("Aguardando 20 segundos antes de tentar novamente...")
                time.sleep(20)
            else:
                log(f"[FALHA] Nao foi possivel sincronizar apos {max_retries} tentativas:\n{err_msg}")
    return False

def main():
    if is_another_instance_running():
        log("Outra instancia do sincronizador ja esta em execucao. Encerrando esta.")
        sys.exit(0)

    write_pid()
    log("===========================================================")
    log("[STARTUP] Mesus Commercial OS Sync Daemon iniciado no boot!")
    log("===========================================================")

    time.sleep(15)
    wait_for_internet(timeout_seconds=90)

    execute_sync()

    log(f"Daemon ativo em background. Proxima sincronizacao automatica em {INTERVAL_SECONDS // 3600} horas.")
    try:
        while True:
            time.sleep(INTERVAL_SECONDS)
            log("[CICLO AGENDADO] Executando sincronizacao periodica em background...")
            execute_sync()
    except (KeyboardInterrupt, SystemExit):
        log("[STOP] Sincronizador finalizado.")
        if os.path.exists(PID_FILE):
            try:
                os.remove(PID_FILE)
            except Exception:
                pass

if __name__ == '__main__':
    main()
