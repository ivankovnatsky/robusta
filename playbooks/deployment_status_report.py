from pydantic import SecretStr

from robusta.api import *
import requests


class ReportParams(BaseModel):
    grafana_api_key: SecretStr
    report_name: str = "Deployment change report"
    fields_to_monitor: List[str] = ["image"]
    delays: List[int]
    reports_panel_urls: List[str]


@action
def report_rendering_task(event: ScheduledExecutionEvent, action_params: ReportParams):
    finding = Finding(
        title=action_params.report_name,
        aggregation_key="report_rendering_task",
    )
    for panel_url in action_params.reports_panel_urls:
        image: requests.models.Response = requests.post(
            GRAFANA_RENDERER_URL,
            data={
                "apiKey": action_params.grafana_api_key.get_secret_value(),
                "panelUrl": panel_url,
            },
        )
        finding.add_enrichment([FileBlock("panel.png", image.content)])
    event.add_finding(finding)


def has_matching_diff(event: DeploymentEvent, fields_to_monitor: List[str]) -> bool:
    all_diffs = event.obj.diff(event.old_obj)
    for diff in all_diffs:
        if is_matching_diff(diff, fields_to_monitor):
            return True
    return False


@action
def deployment_status_report(event: DeploymentEvent, action_params: ReportParams):
    """Export configured reports, every pre-defined period"""
    if event.operation == K8sOperationType.DELETE:
        return

    if event.operation == K8sOperationType.UPDATE:
        if not has_matching_diff(event, action_params.fields_to_monitor):
            return

    logging.info(
        f"Scheduling rendering report. deployment: {event.obj.metadata.name} delays: {action_params.delays}"
    )
    playbook_id = action_hash(
        report_rendering_task,
        action_params,
        {
            "key": f"deployment_status_report_{event.obj.metadata.name}_{event.obj.metadata.namespace}"
        },
    )
    event.get_scheduler().schedule_playbook(
        action_name=report_rendering_task.__name__,
        playbook_id=playbook_id,
        scheduling_params=DynamicDelayRepeat(delay_periods=action_params.delays),
        named_sinks=event.named_sinks,
        action_params=action_params,
        replace_existing=True,
        standalone_task=True,
    )
