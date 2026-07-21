from cli.ucli.contracts.lang_strategies import (
    infer_csharp_method_args,
    infer_java_method_args,
    strategy_for_csharp_type,
    strategy_for_java_type,
)


def test_java_type_strategies_and_infer():
    assert "integers" in strategy_for_java_type("int")
    assert "lists" in strategy_for_java_type("List<String>")
    sig = "public static void foo(int a, List<String> names)"
    args = infer_java_method_args(sig)
    assert ("a", "int") in args and ("names", "List<String>") in args


def test_csharp_type_strategies_and_infer():
    assert "integers" in strategy_for_csharp_type("int")
    assert "lists" in strategy_for_csharp_type("List<string>")
    sig = "public static void Foo(int a, List<string> names)"
    args = infer_csharp_method_args(sig)
    assert ("a", "int") in args and ("names", "List<string>") in args
