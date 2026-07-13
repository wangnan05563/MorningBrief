"""三个问题修复后的功能验证脚本。

问题1：目标时长(target_duration_sec)保存持久化
问题2：参数计算器菜单图标（前端构建已验证，无需 API 测试）
问题3：参数计算器应用到 AI 配置（前端路由传参，通过 API 验证保存逻辑）
"""
import httpx

BASE = "http://127.0.0.1:8000"


def main():
    # 登录
    resp = httpx.post(f"{BASE}/admin/api/v1/auth/login", json={"username": "admin", "password": "admin123"}, timeout=10)
    assert resp.status_code == 200, f"Login failed: {resp.status_code}"
    token = resp.json()["data"]["token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[0] Login OK")

    # ==== 问题1：目标时长持久化 ====
    print("\n=== Problem 1: target_duration_sec persistence ===")

    # 读取当前配置
    resp = httpx.get(f"{BASE}/admin/api/v1/ai/config", headers=headers, timeout=10)
    assert resp.status_code == 200
    data = resp.json()["data"]
    original_duration = data["llm"].get("target_duration_sec", 600)
    print(f"[1.1] Original target_duration_sec: {original_duration}")

    # 修改目标时长为 900 秒并保存
    new_duration = 900 if original_duration != 900 else 750
    save_body = {
        "llm": {
            "api_key": data["llm"]["api_key"],
            "base_url": data["llm"]["base_url"],
            "model": data["llm"]["model"],
            "timeout_sec": data["llm"]["timeout_sec"],
            "retry_attempts": data["llm"]["retry_attempts"],
            "target_duration_sec": new_duration,
        },
        "tts": data["tts"],
        "selected_preset": data["llm"].get("selected_preset", ""),
    }
    resp = httpx.put(f"{BASE}/admin/api/v1/ai/config", headers=headers, json=save_body, timeout=10)
    assert resp.status_code == 200, f"Save failed: {resp.text}"
    print(f"[1.2] Saved target_duration_sec={new_duration}")

    # 重新读取验证持久化
    resp = httpx.get(f"{BASE}/admin/api/v1/ai/config", headers=headers, timeout=10)
    assert resp.status_code == 200
    saved_duration = resp.json()["data"]["llm"]["target_duration_sec"]
    assert saved_duration == new_duration, f"target_duration_sec not persisted: expected {new_duration}, got {saved_duration}"
    print(f"[1.3] Verified persisted: target_duration_sec={saved_duration}")

    # 恢复原始值
    save_body["llm"]["target_duration_sec"] = original_duration
    resp = httpx.put(f"{BASE}/admin/api/v1/ai/config", headers=headers, json=save_body, timeout=10)
    assert resp.status_code == 200
    print(f"[1.4] Restored to original: {original_duration}")

    # ==== 问题3：参数计算器参数同步（API 层面验证 edge_rate 和 target_duration_sec 可同时保存） ====
    print("\n=== Problem 3: Calculator params sync (API level) ===")

    # 模拟参数计算器应用：duration=480, rate=1.5
    # 期望：target_duration_sec=480, edge_rate="+50%"
    resp = httpx.get(f"{BASE}/admin/api/v1/ai/config", headers=headers, timeout=10)
    assert resp.status_code == 200
    data = resp.json()["data"]
    original_edge_rate = data["tts"].get("edge_rate", "")

    save_body = {
        "llm": {
            "api_key": data["llm"]["api_key"],
            "base_url": data["llm"]["base_url"],
            "model": data["llm"]["model"],
            "timeout_sec": data["llm"]["timeout_sec"],
            "retry_attempts": data["llm"]["retry_attempts"],
            "target_duration_sec": 480,
        },
        "tts": {**data["tts"], "edge_rate": "+50%"},
        "selected_preset": data["llm"].get("selected_preset", ""),
    }
    resp = httpx.put(f"{BASE}/admin/api/v1/ai/config", headers=headers, json=save_body, timeout=10)
    assert resp.status_code == 200, f"Save failed: {resp.text}"
    print("[3.1] Saved with calculator params: duration=480, edge_rate=+50%")

    # 验证保存成功
    resp = httpx.get(f"{BASE}/admin/api/v1/ai/config", headers=headers, timeout=10)
    assert resp.status_code == 200
    synced = resp.json()["data"]
    assert synced["llm"]["target_duration_sec"] == 480, f"duration not synced: {synced['llm']['target_duration_sec']}"
    assert synced["tts"]["edge_rate"] == "+50%", f"edge_rate not synced: {synced['tts']['edge_rate']}"
    print(f"[3.2] Verified sync: target_duration_sec={synced['llm']['target_duration_sec']}, edge_rate={synced['tts']['edge_rate']}")

    # 恢复原始值
    save_body["llm"]["target_duration_sec"] = original_duration
    save_body["tts"]["edge_rate"] = original_edge_rate
    resp = httpx.put(f"{BASE}/admin/api/v1/ai/config", headers=headers, json=save_body, timeout=10)
    assert resp.status_code == 200
    print("[3.3] Restored to original values")

    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    main()
