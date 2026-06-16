from checkov.terraform.checks.resource.base_resource_check import BaseResourceCheck
from checkov.common.models.enums import CheckResult


class RequireProjectTag(BaseResourceCheck):
    def __init__(self):
        name = "Ensure all taggable resources have a Project tag"
        id = "CKV_FREELANCE_1"
        supported_resources = [
            "aws_instance",
            "aws_s3_bucket",
            "aws_db_instance",
            "aws_lb",
            "aws_ecr_repository",
            "aws_cloudwatch_log_group",
        ]
        categories = ["CONVENTION"]
        super().__init__(name=name, id=id, categories=categories,
                         supported_resources=supported_resources)

    def scan_resource_conf(self, conf):
        tags = conf.get("tags")
        if tags and isinstance(tags, list):
            tags = tags[0]
        if isinstance(tags, dict) and "Project" in tags:
            return CheckResult.PASSED
        return CheckResult.FAILED


check = RequireProjectTag()