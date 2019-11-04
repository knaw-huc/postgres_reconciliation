from common.helpers import hash_string
from worker.matching.match import Match
from worker.matching.resource import Resource


class AlignmentConfig:
    def __init__(self, job_id, run_match, matches_data, resources_data):
        self.job_id = job_id
        self.run_match = run_match

        self.matches = list(map(lambda match: Match(match, self), matches_data))
        self.resources = list(map(lambda resource: Resource(resource, self), resources_data))

    @property
    def linkset_schema_name(self):
        return 'job_' + str(self.run_match) + '_' + self.job_id

    @property
    def linkset_table_name(self):
        return 'linkset_' + self.job_id + '_' + str(self.run_match)

    @property
    def match_to_run(self):
        return self.get_match_by_id(self.run_match)

    @property
    def resources_to_run(self):
        resources_to_add = [hash_string(resource) for resource in self.match_to_run.resources]
        resources_to_run = []

        resources_added = []
        while resources_to_add:
            resource_to_add = resources_to_add[0]

            if resource_to_add not in resources_added:
                for resource in self.resources:
                    if resource.label == resource_to_add:
                        resources_to_run.append(resource)

                        resources_to_add.remove(resource_to_add)
                        resources_added.append(resource_to_add)
            else:
                resources_to_add.remove(resource_to_add)

        return resources_to_run

    @property
    def has_queued_resources(self):
        for resource in self.resources:
            if resource.view_queued:
                return True

        return False

    def get_match_by_id(self, id):
        for match in self.matches:
            if match.id == id:
                return match

        return None

    def get_resource_by_label(self, label):
        for resource in self.resources:
            if resource.label == label:
                return resource

        return None
