import json

from policy_as_code_agent.utils.llm import (
    generate_sample_values_str,
    get_json_schema_from_content,
)


def test_generate_sample_values_picks_representative():
    # Create a list where the second item is "larger" (more fields) than the first
    sparse_entry = {"name": "sparse", "id": 1}
    rich_entry = {
        "name": "rich",
        "id": 2,
        "details": {"description": "lots of data"},
        "tags": ["a", "b", "c"],
    }

    # Function should pick rich_entry because len(json.dumps(rich_entry)) > len(json.dumps(sparse_entry))
    sample_str = generate_sample_values_str([sparse_entry, rich_entry])
    sample_dict = json.loads(sample_str)

    assert sample_dict.get("name") == "rich"
    assert "details.description" in sample_dict
    assert "tags[]" in sample_dict


def test_generate_sample_values_empty():
    sample_str = generate_sample_values_str([])
    assert sample_str == "{}"


def test_generate_sample_values_traversal():
    surface_value = 1
    nested_value = 2
    deep_value = 3
    list_value_1 = 4

    data = [
        {
            "a": 1,
            "nested": {"b": 2, "deep": {"c": 3}},
            "list_of_objs": [{"d": 4}, {"d": 5}],
        }
    ]

    sample_str = generate_sample_values_str(data)
    sample_dict = json.loads(sample_str)

    assert sample_dict.get("a") == surface_value
    assert sample_dict.get("nested.b") == nested_value
    assert sample_dict.get("nested.deep.c") == deep_value
    assert sample_dict.get("list_of_objs[].d") == list_value_1


def test_get_json_schema_simple():
    content = '[{"name": "Alice", "age": 30}]'
    schema = get_json_schema_from_content(content)
    expected = {"name": "str", "age": "int"}
    assert schema == expected


def test_get_json_schema_nested():
    content = '[{"user": {"id": 1, "details": {"active": true}}}]'
    schema = get_json_schema_from_content(content)
    expected = {"user": {"id": "int", "details": {"active": "bool"}}}
    assert schema == expected


def test_get_json_schema_list():
    content = '[{"tags": ["a", "b"]}]'
    schema = get_json_schema_from_content(content)
    # The util merges list schemas, usually taking the first item's type
    expected = {"tags": ["str"]}
    assert schema == expected


def test_get_json_schema_jsonl():
    content = '{"a": 1}\n{"b": 2}'
    schema = get_json_schema_from_content(content)
    # It merges keys from both lines
    expected = {"a": "int", "b": "int"}
    assert schema == expected
