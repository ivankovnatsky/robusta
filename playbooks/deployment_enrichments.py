from robusta.api import *


def deployment_status_enrichment(deployment: Deployment) -> List[BaseBlock]:
    block_list: List[BaseBlock] = []
    block_list.append(MarkdownBlock("*Deployment status details:*"))
    for condition in deployment.status.conditions:
        block_list.append(MarkdownBlock(f"*{condition.reason} -* {condition.message}"))
    return block_list


@action
def show_deployment_status_enrichment(
    event: ExecutionBaseEvent, params: NamespacedKubernetesObjectParams
):
    deployment: Deployment = Deployment.readNamespacedDeployment(
        params.name, params.namespace
    ).obj
    blocks = deployment_status_enrichment(deployment)
    if blocks:
        finding = Finding(
            title=f"Deployment status - {params.namespace}/{params.name}",
            source=FindingSource.MANUAL,
            aggregation_key="show_deployment_status_enrichment",
        )
        finding.add_enrichment(blocks)
        event.add_finding(finding)
