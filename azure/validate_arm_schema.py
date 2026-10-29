#!/usr/bin/env python3
"""Check ARM wrappers and each concrete resource against pinned official schemas.

This is a local JSON Schema check, not ARM expression evaluation or Azure's
server-side validate/what-if/deploy operation. No Azure credentials are used.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import urllib.request
import warnings


DIRECTORY = Path(__file__).resolve().parent


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate(template_path, cache):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from jsonschema import Draft4Validator, RefResolver
    lock = json.loads((DIRECTORY / "arm-schema-lock.json").read_text())
    cache.mkdir(parents=True, exist_ok=True)
    schemas = {}
    schema_hashes = {}
    for name, entry in lock["files"].items():
        path = cache / name
        if not path.exists():
            data = urllib.request.urlopen(entry["url"], timeout=30).read(4 * 1024 * 1024)
            if digest(data) != entry["sha256"]:
                raise ValueError("Official schema hash mismatch: " + name)
            path.write_bytes(data)
        data = path.read_bytes()
        if digest(data) != entry["sha256"]:
            raise ValueError("Cached schema hash mismatch: " + name)
        schemas[name] = json.loads(data)
        schema_hashes[name] = entry["sha256"]
    root = schemas["2019-04-01-deploymentTemplate.json"]
    store = {}
    for schema in schemas.values():
        store[schema["id"].rstrip("#")] = schema
        store[schema["id"]] = schema

    def blocked(url):
        raise ValueError("Unpinned schema resolution refused: " + url)

    resolver = RefResolver.from_schema(root, store=store, handlers={"http": blocked, "https": blocked})
    checks = []
    native_phase = True
    native_failures = []

    def check(instance, schema, label):
        validator = Draft4Validator(schema, resolver=resolver)
        errors = sorted(validator.iter_errors(instance), key=lambda error: list(map(str, error.path)))
        if errors:
            if native_phase:
                def leaves(error):
                    if error.context:
                        return [leaf for child in error.context for leaf in leaves(child)]
                    return [{"instance_path": list(error.absolute_path), "schema_path": list(error.absolute_schema_path), "message": error.message}]
                native_failures.append({"check": label, "errors": [leaf for error in errors for leaf in leaves(error)]})
                return
            error = errors[0]
            raise ValueError(f"{label}: {'/'.join(map(str, error.path))}: {error.message}")
        checks.append(label)

    def walk(template, label):
        # The root schema's generic resource union follows generated schemas for
        # all historical API versions. Avoid that union: retain every wrapper
        # field, then validate each real resource using its exact API below.
        wrapper = copy.deepcopy(template)
        wrapper["resources"] = []
        check(wrapper, root, label + ":template-wrapper")
        for index, resource in enumerate(template["resources"]):
            provider, *segments = resource["type"].split("/")
            schema_name = resource["apiVersion"] + "-" + provider + ".json"
            if schema_name not in schemas:
                raise ValueError("Resource API not in schema lock: " + schema_name)
            api = schemas[schema_name]
            definition = "_".join(segments)
            exact = {"allOf": [{"$ref": root["id"].rstrip("#") + "#/definitions/resourceBase"}, {"$ref": api["id"].rstrip("#") + "#/resourceDefinitions/" + definition}]}
            name = f"{label}:resources/{index}:{resource['type']}@{resource['apiVersion']}"
            check(resource, exact, name)
            if resource["type"] == "Microsoft.Resources/deployments":
                nested = resource.get("properties", {}).get("template")
                if isinstance(nested, dict):
                    walk(nested, name + ":nested")

    template_bytes = template_path.read_bytes()
    walk(json.loads(template_bytes), "root")
    native_checks = checks.copy()
    checks.clear()
    native_phase = False
    # Microsoft's generated Resources schema rejects legitimate deployment
    # parameters because oneOf [{}, expression] matches every expression twice.
    # Its scope enum also omits the lowercase spelling used by ARM's guide.
    # Adapt these two exact locations; record the changes in the receipt.
    resources_schema = schemas["2022-09-01-Microsoft.Resources.json"]
    parameter_value = resources_schema["definitions"]["DeploymentParameter"]["properties"]["value"]
    if parameter_value["oneOf"] != [{}, {"$ref": "https://schema.management.azure.com/schemas/common/definitions.json#/definitions/expression"}]:
        raise ValueError("Resources schema compatibility precondition changed")
    parameter_value["anyOf"] = parameter_value.pop("oneOf")
    scope_enum = resources_schema["definitions"]["ExpressionEvaluationOptions"]["properties"]["scope"]["oneOf"][0]["enum"]
    if scope_enum != ["NotSpecified", "Outer", "Inner"]:
        raise ValueError("Resources scope schema compatibility precondition changed")
    scope_enum.extend(["inner", "outer"])
    adaptations = [{"file": "2022-09-01-Microsoft.Resources.json", "path": "definitions/DeploymentParameter/properties/value", "change": "oneOf to anyOf for the empty-schema plus ARM-expression union"}, {"file": "2022-09-01-Microsoft.Resources.json", "path": "definitions/ExpressionEvaluationOptions/properties/scope", "change": "accept documented inner/outer alongside generated enum Inner/Outer"}]
    walk(json.loads(template_bytes), "root")
    return {"schema": "thox.azure.arm-schema-validation.v1", "result": "passed_with_documented_schema_adaptations", "template_sha256": digest(template_bytes), "schema_repository": lock["repository"], "schema_revision": lock["revision"], "schema_sha256": schema_hashes, "native_strict_schema_validation": {"result": "failed" if native_failures else "passed", "passed_checks": native_checks, "failures": native_failures}, "schema_adaptations": adaptations, "checks": checks, "boundaries": {"check": "official template wrappers plus exact API resource schemas, including nested deployment, with two explicitly recorded Resources schema compatibility changes", "arm_expression_evaluation": "not_performed", "azure_server_validation": "not_run", "azure_deployment": "not_run"}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", type=Path, default=DIRECTORY / "azuredeploy.json")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.template, args.cache)
    except (ImportError, OSError, ValueError, KeyError) as error:
        parser.exit(2, f"Stopped: {error}\n")
    output = json.dumps(result, indent=2) + "\n"
    if args.receipt:
        args.receipt.write_text(output)
    print(output, end="")


if __name__ == "__main__":
    main()
