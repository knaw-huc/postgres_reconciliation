export default {
    data() {
        return {
            job: null,
            alignments: [],
            clusterings: [],
            resources: [],
            matches: [],
            datasets: null,
        };
    },
    methods: {
        addResource() {
            this.resources.unshift({
                dataset_id: '',
                collection_id: '',
                id: findId(this.resources),
                filter: {
                    type: 'AND',
                    conditions: [],
                },
                limit: -1,
                related: [],
                related_array: false,
            });
        },

        addMatch() {
            this.matches.unshift({
                id: findId(this.matches),
                is_association: false,
                label: 'Alignment ' + (this.matches.length + 1),
                sources: [],
                targets: [],
                properties: [],
                match_against: null,
                methods: {
                    type: 'AND',
                    conditions: [],
                },
            });
        },

        duplicateResource(resource) {
            const index = this.resources.findIndex(res => res.id === resource.id);
            const newId = findId(this.resources);

            const duplicate = copy(resource);
            const newResource = {
                ...duplicate,
                id: newId,
                label: undefined,
            };

            getRecursiveConditions(newResource.filter.conditions)
                .forEach(condition => condition.property[0] = newId);

            this.resources.splice(index, 0, newResource);
        },

        duplicateMatch(match) {
            const index = this.matches.findIndex(m => m.id === match.id);
            const duplicate = copy(match);
            this.matches.splice(index, 0, {
                ...duplicate,
                id: findId(this.matches),
                label: 'Alignment ' + (this.matches.length + 1),
            });
        },

        getResourceById(resourceId, resources = this.resources) {
            return resources.find(res =>
                (isId(resourceId) && res.id === parseInt(resourceId)) || res.label === resourceId);
        },

        getResourceByDatasetId(datasetId, resources = this.resources) {
            return resources.find(res => res.dataset_id === datasetId);
        },

        getMatchById(matchId, matches = this.matches) {
            return matches.find(match => (isId(matchId) && match.id === parseInt(matchId)) || match.label === matchId);
        },

        createTargetsForProperties(properties) {
            return properties.reduce((targets, prop) => {
                const resource = this.getResourceById(prop[0]);

                let resourceTarget = targets.find(t => t.graph === resource.dataset_id);
                if (!resourceTarget) {
                    resourceTarget = {graph: resource.dataset_id, data: []};
                    targets.push(resourceTarget);
                }

                let entityTarget = resourceTarget.data.find(d => d.entity_type === resource.collection_id);
                if (!entityTarget) {
                    entityTarget = {entity_type: resource.collection_id, properties: []};
                    resourceTarget.data.push(entityTarget);
                }

                if (prop[prop.length - 1] === '__value__')
                    entityTarget.properties.push(prop.slice(1, -1));
                else
                    entityTarget.properties.push(prop.slice(1));

                return targets;
            }, []);
        },

        createReferencesForProperty(property, resources) {
            const baseReferencedResource = this.getResourceById(property[0], resources);
            property[0] = baseReferencedResource.label;

            if (property.length < 3)
                return property;

            if (property[2] === '__value__')
                return property.slice(0, 2);

            const referencedResource = {
                label: this.$utilities.md5(property[0] + property[1] + property[2]),
                collection_id: property[2],
                dataset_id: baseReferencedResource.dataset_id,
                related: []
            };

            if (!resources.find(rc => rc.label === referencedResource.label))
                resources.push(referencedResource);

            const relation = {
                resource: referencedResource.label,
                local_property: property[1],
                remote_property: 'uri'
            };

            if (!baseReferencedResource.related.find(rel => JSON.stringify(rel) === JSON.stringify(relation)))
                baseReferencedResource.related.push(relation);

            if (baseReferencedResource.related.length > 1)
                baseReferencedResource.related_array = true;

            const newProperty = [referencedResource.label, property[3], ...property.slice(4)];
            return this.createReferencesForProperty(newProperty, resources);
        },

        async submit() {
            const resources = copy(this.resources);
            const matches = copy(this.matches);

            matches.forEach(match => {
                ['sources', 'targets'].forEach(key => {
                    match[key].forEach((resourceId, index) => {
                        if (isId(resourceId))
                            match[key][index] = this.getResourceById(resourceId).label;
                    });
                });

                getRecursiveConditions(match.methods.conditions).forEach(condition => {
                    ['sources', 'targets'].forEach(key => {
                        Object.keys(condition[key]).forEach(resourceId => {
                            condition[key][resourceId].forEach((property, index) => {
                                condition[key][resourceId][index].property =
                                    this.createReferencesForProperty(property.property, resources);
                            });

                            condition[key][this.getResourceById(resourceId).label] = condition[key][resourceId];
                            delete condition[key][resourceId];
                        });
                    });
                });

                match.value_targets = this.createTargetsForProperties(match.properties);
                delete match.properties;
            });

            resources.forEach(resource => {
                if (resource.filter && resource.filter.conditions && resource.filter.conditions.length > 0) {
                    getRecursiveConditions(resource.filter.conditions).forEach(condition => {
                        condition.property = this.createReferencesForProperty(condition.property, resources);
                    });
                }
                else
                    delete resource.filter;
            });

            resources.forEach(resource => {
                if (resource.related) {
                    resource.related.forEach(related => {
                        if (isId(related.resource))
                            related.resource = this.getResourceById(related.resource).label;

                        related.local_property = [related.local_property];
                        related.remote_property = [related.remote_property];
                    });

                    if (resource.related_array)
                        resource.related = [resource.related];
                }

                delete resource.related_array;
                delete resource.id;
            });

            await this.updateJob({
                job_id: this.job.job_id,
                job_title: this.job.job_title,
                job_description: this.job.job_description,
                resources: resources,
                matches: matches,
                resources_original: this.resources,
                matches_original: this.matches,
            });
        },

        async loadJob(jobId) {
            const job = await callApi('/job/' + jobId);
            job.created_at = new Date(job.created_at);
            job.updated_at = new Date(job.updated_at);
            this.job = job;

            if (this.job.resources_form_data)
                this.resources = copy(this.job.resources_form_data);

            if (this.job.mappings_form_data)
                this.matches = copy(this.job.mappings_form_data);

            await Promise.all([this.loadAlignments(), this.loadClusterings()]);
        },

        async loadAlignments() {
            const alignments = await callApi(`/job/${this.job.job_id}/alignments`);
            alignments.forEach(alignment => {
                alignment.requested_at = new Date(alignment.requested_at);
                alignment.processing_at = new Date(alignment.processing_at);
                alignment.finished_at = new Date(alignment.finished_at);
            });
            this.alignments = alignments;
        },

        async loadClusterings() {
            const clusterings = await callApi(`/job/${this.job.job_id}/clusterings`);
            clusterings.forEach(clustering => {
                clustering.requested_at = new Date(clustering.requested_at);
                clustering.processing_at = new Date(clustering.processing_at);
                clustering.finished_at = new Date(clustering.finished_at);
            });
            this.clusterings = clusterings;
        },

        async createJob(inputs) {
            const data = await callApi("/job/create/", inputs);
            return data.job_id;
        },

        async updateJob(jobData) {
            await callApi("/job/update/", jobData);
        },

        async runAlignment(alignment, restart) {
            await this.submit();
            return callApi(`/job/${this.job.job_id}/run_alignment/${alignment}`, {restart});
        },

        async killAlignment(alignment) {
            return callApi(`/job/${this.job.job_id}/kill_alignment/${alignment}`, {});
        },

        async getAlignment(alignment, clusterId = undefined, limit = undefined, offset = 0) {
            const params = [];
            if (clusterId) params.push(`cluster_id=${clusterId}`);
            if (limit) params.push(`limit=${limit}`);
            if (offset) params.push(`offset=${offset}`);

            return callApi(`/job/${this.job.job_id}/alignment/${alignment}?${params.join('&')}`);
        },

        async getClusters(alignment, association, limit = undefined, offset = 0) {
            const params = [];
            if (association) params.push(`association=${association}`);
            if (limit) params.push(`limit=${limit}`);
            if (offset) params.push(`offset=${offset}`);

            return callApi(`/job/${this.job.job_id}/clusters/${alignment}?${params.join('&')}`);
        },

        async runClustering(alignment, association_file) {
            return callApi(`/job/${this.job.job_id}/run_clustering/${alignment}`, {association_file});
        },

        async getClusterGraphs(alignment, clusterId,
                               getCluster = undefined, getClusterCompact = undefined, getReconciliation = undefined) {
            const params = [];
            if (getCluster !== undefined) params.push(`get_cluster=${getCluster}`);
            if (getClusterCompact !== undefined) params.push(`get_cluster_compact=${getClusterCompact}`);
            if (getReconciliation !== undefined) params.push(`get_reconciliation=${getReconciliation}`);

            return callApi(`/job/${this.job.job_id}/cluster/${alignment}/${clusterId}/graph?${params.join('&')}`);
        },

        async validateLink(alignment, source, target, valid) {
            return callApi(`/job/${this.job.job_id}/validate/${alignment}`, {source, target, valid});
        },

        async getAssociationFiles() {
            return callApi("/association_files");
        },

        async loadDatasets() {
            if (this.datasets)
                return;

            const datasets = await callApi("/datasets");

            // Make internal references for referenced collections
            Object.keys(datasets).forEach(datasetName => {
                const dataset = datasets[datasetName];

                Object.keys(dataset.collections).forEach(collectionName => {
                    const collection = dataset.collections[collectionName];

                    Object.keys(collection).forEach(propertyName => {
                        const property = collection[propertyName];

                        if (property.hasOwnProperty('referencedCollections')) {
                            const referencedCollections = property.referencedCollections;
                            property.referencedCollections = {};

                            referencedCollections.forEach(name =>
                                property.referencedCollections[name] = dataset.collections[name]);
                        }
                    });
                });
            });

            this.datasets = datasets;
        },
    },
};

function copy(obj) {
    return JSON.parse(JSON.stringify(obj));
}

function isId(id) {
    return Number.isInteger(id) || /^\d+$/.test(id);
}

function findId(objs) {
    let latestId = -1;
    objs.forEach(obj => {
        if (obj.id > latestId) latestId = obj.id;
    });
    return latestId + 1;
}

function getRecursiveConditions(conditionsGroup) {
    let conditions;
    if (Array.isArray(conditionsGroup))
        conditions = conditionsGroup;
    else if (Array.isArray(conditionsGroup.conditions))
        conditions = conditionsGroup.conditions;

    if (conditions)
        return conditions.reduce((acc, condition) => acc.concat(getRecursiveConditions(condition)), []);

    return [conditionsGroup];
}

async function callApi(path, body) {
    if (body) {
        const response = await fetch(path, {
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
            },
            method: 'POST',
            body: JSON.stringify(body)
        });

        return response.json();
    }

    const response = await fetch(path);

    return response.json();
}