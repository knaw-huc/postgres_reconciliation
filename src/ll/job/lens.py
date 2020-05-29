from ll.job.lens_elements import LensElements


class Lens:
    def __init__(self, data, job):
        self._data = data
        self._job = job
        self._specs = None

    @property
    def id(self):
        return self._data['id']

    @property
    def specs(self):
        if not self._specs:
            specs = self._data['specs']
            self._specs = LensElements(specs['elements'], specs['type'], self._job)
        return self._specs

    @property
    def select_sql(self):
        return self.specs.select_sql

    @property
    def select_validity_sql(self):
        return self.specs.select_validity_sql

    @property
    def linksets(self):
        return self.specs.linksets

    @property
    def lenses(self):
        return self.specs.lenses

    @property
    def properties(self):
        return self._data['properties']
