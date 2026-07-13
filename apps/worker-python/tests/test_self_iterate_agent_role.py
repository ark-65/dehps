from pathlib import Path


def test_self_iterate_prompt_is_single_role_and_fail_closed() -> None:
    prompt = (Path(__file__).resolve().parents[3] / "scripts/hourly_self_iterate.sh").read_text()
    assert "当前角色：Engineering Agent" in prompt
    assert "一次自迭代只能声明并使用一个角色" in prompt
    assert "no_authorized_agent_request" in prompt
    assert "未批准的 Request 不得执行" in prompt
    assert "Research Agent 模式不得修改文件" in prompt
    assert "production 操作必须由已批准的 Operator Request 驱动" in prompt
