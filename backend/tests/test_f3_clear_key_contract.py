"""F3：清空 API Key 这件事，代码、文档、界面三处口径必须一致（FR-UX-101）

原缺陷是「契约与实现矛盾」：三个 `_normalize_*` 的 docstring 都写「空字符串清除」，
实现却是 `if api_key and not _is_masked(...)`——空串压根不进 updates，旧 Key 原地不动。
用户把 Key 框清空 → 保存 → 提示成功 → 重进页面脱敏值还在，且界面上没有任何说明。

这里把**真实语义**钉住（留空 = 不修改），而不是把它改成「留空即删密钥」——因为前端在
`AIConfig.vue` 里本来就把脱敏值折算成空串回传（`key.startsWith('****') ? '' : key`），
一旦后端把空串当清除，用户只改 base_url 也会把线上密钥抹掉。
清除密钥另有通道：`POST /ai/reset-config`（界面文案「恢复初始配置」）。
"""
from app.services.ai_config_service import AIConfigService


def _norm():
    # 三个归一化函数都是纯映射，不需要真连接；只有 docstring/分支需要被测
    svc = AIConfigService.__new__(AIConfigService)
    return svc


def test_empty_api_key_is_treated_as_unchanged():
    svc = _norm()
    for name in ("_normalize_llm", "_normalize_tts", "_normalize_image"):
        out = getattr(svc, name)({"api_key": ""})
        key_cols = [k for k in out if "api_key" in k or k.endswith("appkey")]
        assert not key_cols, f"{name} 把空串当成清除写进了 {key_cols}，会抹掉线上密钥"


def test_masked_api_key_is_treated_as_unchanged():
    svc = _norm()
    for name in ("_normalize_llm", "_normalize_tts", "_normalize_image"):
        out = getattr(svc, name)({"api_key": "****abcd"})
        key_cols = [k for k in out if "api_key" in k or k.endswith("appkey")]
        assert not key_cols, f"{name} 把脱敏值写进了 {key_cols}"


def test_real_api_key_is_written():
    """反过来也得钉住：留空是唯一的不改口径，传真值必须落库，否则这条门会把修复也门掉。"""
    svc = _norm()
    assert svc._normalize_llm({"api_key": "sk-real-new"})["llm_api_key"] == "sk-real-new"
    assert svc._normalize_tts({"api_key": "tts-real-new"})["tts_api_key"] == "tts-real-new"


def test_non_key_fields_still_submit_with_empty_api_key():
    """清空 Key 不影响同表单其它字段照常保存——这是「只改 base_url」的真实形态。"""
    svc = _norm()
    out = svc._normalize_llm({"api_key": "", "base_url": "https://new.example", "model": "gpt-4o"})
    assert out["llm_base_url"] == "https://new.example"
    assert "llm_api_key" not in out


def test_docstrings_no_longer_claim_clear_on_empty():
    """F3 的标题就是「契约与实现矛盾」，所以 docstring 本身也在被测范围内。"""
    import inspect
    import re

    import app.services.ai_config_service as ai_mod
    import app.services.cos_config_service as cos_mod

    # COS 的 update_config 是同一类口径矛盾（`if secret_id and not _is_masked(...)`
    # 也不会因空串而清除），一并钉住，免得只修了被点名的那一处
    for mod in (ai_mod, cos_mod):
        assert not re.search(r"空字符串(视为)?清除", inspect.getsource(mod)), (
            f"{mod.__name__} 的 docstring 承诺「清空即删除」，实现并不这么做"
        )

    # update_config 是路由直接调的入口，它的 docstring 是最容易被运维读到的一段，
    # 不能只修三个 _normalize_* 而把门面留在旧口径上
    for name in ("update_config", "_normalize_llm", "_normalize_tts", "_normalize_image"):
        doc = inspect.getdoc(getattr(AIConfigService, name)) or ""
        assert "留空" in doc and "不修改" in doc.replace("未修改", "不修改"), f"{name} 的 docstring 没交代留空的语义"
        assert "reset-config" in doc, f"{name} 没指路真正的清除通道，用户只能靠猜"


def test_every_api_key_write_site_is_truthiness_guarded():
    """留空即不写这条规则要在**所有** 4 个写入点成立，包括预设配置那条路径。

    `_save_preset_config` 与三个 `_normalize_*` 共用同一句 `if api_key and not _is_masked(api_key)`，
    少盯一处，就会出现「主配置没事、切预设时把预设里的 Key 抹成空串」。
    """
    import inspect
    import re

    import app.services.ai_config_service as ai_mod

    src = inspect.getsource(ai_mod)
    guarded = re.findall(r"if api_key and not _is_masked\(api_key\):", src)
    assert len(guarded) == 4, f"受 guard 的写入点从 4 处变成 {len(guarded)} 处，本用例要跟着一处处的语义重看"
    assert not re.search(r"if not _is_masked\(api_key\):", src), (
        "出现了不看空值的脱敏判断，空串会被当成新值写入"
    )
