from elasticuma import ElasticUMA

client = ElasticUMA()
model = client.model("qwen36")

if not model.installed:
    plan = client.plan_setup(model.id)
    raise SystemExit(
        f"{model.display_name} is not installed. Review this plan first:\n{plan.as_dict()}"
    )

result = client.generate(model.id, "Explain unified memory in simple language.")
print(result.text)
