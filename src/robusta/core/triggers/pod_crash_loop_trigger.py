from ..discovery.top_service_resolver import TopServiceResolver
from ...core.playbooks.base_trigger import TriggerEvent
from ...integrations.kubernetes.autogenerated.triggers import PodUpdateTrigger, PodChangeEvent
from ...integrations.kubernetes.base_triggers import K8sTriggerEvent
from ...utils.rate_limiter import RateLimiter


class PodCrashLoopTrigger(PodUpdateTrigger):
    rate_limit: int = 3600
    restart_reason: str = None
    restart_count: int = 2

    """
    :var rate_limit: Limit firing to once every `rate_limit` seconds 
    :var restart_reason: Limit restart loops for this specific reason. If omitted, all restart reasons will be included.
    :var restart_count: Fire only after the specified number of restarts 
    """

    def __init__(
            self,
            name_prefix: str = None,
            namespace_prefix: str = None,
            labels_selector: str = None,
            rate_limit: int = 3600,
            restart_reason: str = None,
            restart_count: int = 2,
    ):
        super().__init__(
            name_prefix=name_prefix,
            namespace_prefix=namespace_prefix,
            labels_selector=labels_selector,
        )
        self.rate_limit = rate_limit
        self.restart_reason = restart_reason
        self.restart_count = restart_count

    def should_fire(self, event: TriggerEvent, playbook_id: str):
        should_fire = super().should_fire(event, playbook_id)
        if not should_fire:
            return should_fire

        if not isinstance(event, K8sTriggerEvent):
            return False

        exec_event = self.build_execution_event(event, {})

        if not isinstance(exec_event, PodChangeEvent):
            return False

        pod = exec_event.get_pod()

        all_statuses = pod.status.containerStatuses + pod.status.initContainerStatuses
        crashing = [
            container_status
            for container_status in all_statuses
            if container_status.state.waiting is not None
            and container_status.restartCount >= self.restart_count  # report only after the restart_count restart
            and (self.restart_reason is None or self.restart_reason in container_status.state.waiting.reason)
        ]

        if not crashing:
            return False

        # Perform a rate limit for this pod according to the rate_limit parameter
        name = pod.metadata.ownerReferences[0].name if pod.metadata.ownerReferences else pod.metadata.name
        namespace = pod.metadata.namespace
        return RateLimiter.mark_and_test(
            f"PodCrashLoopTrigger_{playbook_id}",
            namespace + ":" + name,
            self.rate_limit,
        )