<template>
  <card :id="'linkset_spec_' + linksetSpec.id" type="linkset_specs" :res-id="linksetSpec.id" v-model="linksetSpec.label"
        :has-error="errors.length > 0" :has-handle="true" :has-extra-row="!!linkset"
        @show="onToggle(true)" @hide="onToggle(false)">
    <template v-slot:title-columns>
      <div v-if="!isOpen" class="col-auto">
        <b-button variant="info" @click="$emit('duplicate', linksetSpec)">Duplicate</b-button>
      </div>

      <div v-if="linksetStatus === 'downloading' || linksetStatus === 'running'" class="col-auto">
        <b-button variant="danger" @click="killLinkset">
          Stop
        </b-button>
      </div>

      <div v-if="clusteringStatus === 'running'" class="col-auto">
        <b-button variant="danger" @click="killClustering">
          Stop
        </b-button>
      </div>

      <div v-if="!linkset || linksetStatus === 'failed'" class="col-auto">
        <b-button variant="info" @click="runLinkset()">
          Run
          <template v-if="linksetStatus === 'failed'">again</template>
        </b-button>
      </div>

      <div v-if="linksetStatus === 'done' && linkset.distinct_links_count > 0" class="col-auto">
        <button v-if="clustering && clustering !== 'running'" type="button" class="btn btn-info my-1"
                @click="runClustering($event)" :disabled="association === ''"
                :title="association === '' ? 'Choose an association first' : ''">
          Reconcile
          <template v-if="clusteringStatus === 'failed'">again</template>
        </button>

        <button v-else-if="!clustering" type="button" class="btn btn-info my-1" @click="runClustering($event)">
          Cluster
          <template v-if="association !== ''"> &amp; Reconcile</template>
          <template v-if="clusteringStatus === 'failed'">again</template>
        </button>
      </div>

      <div v-if="linksetStatus === 'done' && linkset.distinct_links_count > 0 && $root.associationFiles"
           class="col-auto">
        <select class="col-auto form-control association-select my-1" v-model="association"
                :id="'linkset_' + linksetSpec.id + '_association'">
          <option value="">No association</option>
          <option v-for="associationFileName in $root.associationFiles" :value="associationFileName">
            {{ associationFileName }}
          </option>
        </select>
      </div>

      <div v-if="!isOpen" class="col-auto">
        <button-delete @click="$emit('remove')" title="Delete this linkset" :disabled="!allowDelete"/>
      </div>
    </template>

    <template v-slot:columns>
      <div v-if="linkset" class="col">
        <status :linkset-spec="linksetSpec"/>
      </div>
    </template>

    <sub-card label="Description">
      <textarea class="form-control mt-3" :id="'description_' + linksetSpec.id" v-model="linksetSpec.description">
      </textarea>

      <small class="form-text text-muted mt-2">
        Provide a description for this linkset
      </small>
    </sub-card>

    <fieldset :disabled="!!linkset">
      <sub-card label="Sources" :has-info="true" add-button="Add an Entity-type Selection as a Source"
                :hasError="errors.includes('sources') || errors.includes('sources_select')"
                @add="addEntityTypeSelection('sources')">
        <template v-slot:info>
          <linkset-spec-sources-info/>
        </template>

        <div class="row pl-5 mt-2">
          <div class="col">
            <entity-type-selection
                v-for="(source, index) in linksetSpec.sources"
                :key="index"
                :id="'source_' + index"
                :linkset-spec="linksetSpec"
                :entity-type-selection="$root.getEntityTypeSelectionById(source)"
                selection-key="sources"
                @input="updateEntityTypeSelection('sources', index, $event)"
                @remove="deleteEntityTypeSelection('sources', index)"
                ref="sourceComponents"/>

            <div class="invalid-feedback" v-bind:class="{'is-invalid': errors.includes('sources')}">
              Please provide at least one source
            </div>
          </div>
        </div>
      </sub-card>

      <sub-card label="Targets" :has-info="true" add-button="Add an Entity-type Selection as a Target"
                :hasError="errors.includes('targets') || errors.includes('targets_select')"
                @add="addEntityTypeSelection('targets', $event)">
        <template v-slot:info>
          <linkset-spec-targets-info/>
        </template>

        <div class="row pl-5 mt-2">
          <div class="col">
            <entity-type-selection
                v-for="(target, index) in linksetSpec.targets"
                :key="index"
                :id="'target_' + index"
                :linkset-spec="linksetSpec"
                :entity-type-selection="$root.getEntityTypeSelectionById(target)"
                selection-key="targets"
                @input="updateEntityTypeSelection('targets', index, $event)"
                @remove="deleteEntityTypeSelection('targets', index)"
                ref="targetComponents"/>

            <div class="invalid-feedback" v-bind:class="{'is-invalid': errors.includes('targets')}">
              Please provide at least one target
            </div>
          </div>
        </div>
      </sub-card>

      <sub-card label="Matching Methods" :has-columns="true" :hasError="errors.includes('matching-methods')">
        <template v-slot:columns>
          <div v-if="useFuzzyLogic" class="col-auto form-inline">
            Threshold
            <range class="ml-3" :id="'linkset_threshold_' + linksetSpec.id" v-model.number="linksetSpec.threshold"/>
          </div>

          <div class="col-auto">
            <div class="custom-control custom-switch">
              <input type="checkbox" class="custom-control-input" autocomplete="off"
                     :id="'fuzzy_linkset_' + linksetSpec.id" v-model="useFuzzyLogic"/>
              <label class="custom-control-label" :for="'fuzzy_linkset_' + linksetSpec.id">Use fuzzy logic</label>
            </div>
          </div>
        </template>

        <logic-box :element="linksetSpec.methods" elements-name="conditions" :is-root="true"
                   :should-have-elements="true" group="linkset-filters"
                   :uid="'linkset_' + linksetSpec.id  + '_group_0'"
                   :options="useFuzzyLogic ? fuzzyLogicOptions : undefined"
                   :option-groups="useFuzzyLogic ? fuzzyLogicOptionGroups : undefined"
                   validate-method-name="validateCondition" empty-elements-text="No conditions"
                   validation-failed-text="Please provide at least one condition" v-slot="curCondition"
                   @add="addCondition($event)" ref="matchingMethodGroupComponent">
          <condition
              :condition="curCondition.element" :index="curCondition.index"
              :id="linksetSpec.id + '_' + curCondition.index" :useFuzzyLogic="useFuzzyLogic"
              @add="curCondition.add()" @remove="curCondition.remove()"/>
        </logic-box>
      </sub-card>
    </fieldset>
  </card>
</template>

<script>
    import {EventBus} from "@/eventbus";
    import props from "@/utils/props";
    import ValidationMixin from '@/mixins/ValidationMixin';

    import LinksetSpecSourcesInfo from '../../info/LinksetSpecSourcesInfo';
    import LinksetSpecTargetsInfo from '../../info/LinksetSpecTargetsInfo';
    import MatchingMethodsInfo from '../../info/MatchingMethodsInfo';

    import Status from "./Status";
    import EntityTypeSelection from "./EntityTypeSelection";
    import Condition from "./Condition";

    import LogicBox from "../../helpers/LogicBox";

    export default {
        name: "Linkset",
        mixins: [ValidationMixin],
        components: {
            LinksetSpecSourcesInfo,
            LinksetSpecTargetsInfo,
            MatchingMethodsInfo,
            Status,
            EntityTypeSelection,
            Condition,
            LogicBox
        },
        props: {
            linksetSpec: Object,
            allowDelete: Boolean,
        },
        data() {
            return {
                association: '',
                isOpen: false,
                useFuzzyLogic: false,
                tNorms: Object.keys(props.tNorms),
                tConorms: Object.keys(props.tConorms),
                fuzzyLogicOptions: {...props.tNorms, ...props.tConorms},
                fuzzyLogicOptionGroups: props.fuzzyLogicOptionGroups,
            };
        },
        computed: {
            linkset() {
                return this.$root.linksets.find(linkset => linkset.spec_id === this.linksetSpec.id);
            },

            clustering() {
                return this.$root.clusterings.find(clustering =>
                    clustering.spec_type === 'linkset' && clustering.spec_id === this.linksetSpec.id);
            },

            linksetStatus() {
                return this.linkset ? this.linkset.status : null;
            },

            clusteringStatus() {
                return this.clustering ? this.clustering.status : null;
            },
        },
        methods: {
            validateLinkset() {
                const sourcesValid = this.validateField('sources', this.linksetSpec.sources.length > 0);
                const targetsValid = this.validateField('targets', this.linksetSpec.targets.length > 0);

                const sourcesSelectValid = this.validateField('sources_select',
                    !this.$refs.sourceComponents
                        .map(sourceComponent => sourceComponent.validateEntityTypeSelection())
                        .includes(false)
                );
                const targetsSelectValid = this.validateField('targets_select',
                    !this.$refs.targetComponents
                        .map(targetComponent => targetComponent.validateEntityTypeSelection())
                        .includes(false)
                );

                let matchingMethodGroupValid = true;
                if (this.$refs.matchingMethodGroupComponent)
                    matchingMethodGroupValid = this.$refs.matchingMethodGroupComponent.validateLogicBox();
                matchingMethodGroupValid = this.validateField('matching-methods', matchingMethodGroupValid);

                return sourcesValid && targetsValid
                    && sourcesSelectValid && targetsSelectValid && matchingMethodGroupValid;
            },

            onToggle(isOpen) {
                this.isOpen = isOpen;
                isOpen ? this.$emit('show') : this.$emit('hide');
            },

            addCondition(group) {
                group.conditions.push({
                    method_name: '',
                    method_config: {},
                    method_sim_name: null,
                    method_sim_config: {},
                    method_sim_normalized: false,
                    list_threshold: 0,
                    list_threshold_unit: 'matches',
                    t_conorm: 'MAXIMUM_T_CONORM',
                    threshold: 0,
                    sources: this.linksetSpec.sources
                        .filter(entityTypeSelection => entityTypeSelection !== '')
                        .map(entityTypeSelection => ({
                            entity_type_selection: entityTypeSelection,
                            property: [''],
                            transformers: []
                        })),
                    targets: this.linksetSpec.targets
                        .filter(entityTypeSelection => entityTypeSelection !== '')
                        .map(entityTypeSelection => ({
                            entity_type_selection: entityTypeSelection,
                            property: [''],
                            transformers: []
                        })),
                });
            },

            addEntityTypeSelection(key) {
                this.linksetSpec[key].push('');
            },

            updateEntityTypeSelection(key, index, id) {
                const oldId = this.linksetSpec[key][index];

                this.$set(this.linksetSpec[key], index, id);
                this.$root.getRecursiveElements(this.linksetSpec.methods, 'conditions').forEach(condition => {
                    condition[key].push({entity_type_selection: id, property: [''], transformers: []});
                });

                this.updateProperties(oldId, id);
            },

            deleteEntityTypeSelection(key, index) {
                const id = this.linksetSpec[key][index];

                this.$root.getRecursiveElements(this.linksetSpec.methods, 'conditions').forEach(condition => {
                    condition[key]
                        .map((condition, idx) => condition.entity_type_selection === id ? idx : null)
                        .filter(idx => idx !== null)
                        .sort((idxA, idxB) => idxA > idxB ? -1 : 1)
                        .forEach(idx => condition[key].splice(idx, 1));
                });
                this.$delete(this.linksetSpec[key], index);

                this.updateProperties(id);
            },

            updateProperties(oldEntityTypeSelection, newEntityTypeSelection) {
                const sourcesHasValue = this.linksetSpec.sources.find(source => source === oldEntityTypeSelection);
                const targetsHasValue = this.linksetSpec.targets.find(target => target === oldEntityTypeSelection);
                const oldValueIndex = this.linksetSpec.properties
                    .findIndex(prop => prop.entity_type_selection === oldEntityTypeSelection);

                if ((oldValueIndex >= 0) && !sourcesHasValue && !targetsHasValue)
                    this.linksetSpec.properties.splice(oldValueIndex, 1);

                if ((newEntityTypeSelection !== undefined) &&
                    !this.linksetSpec.properties.find(prop => prop.entity_type_selection === newEntityTypeSelection))
                    this.linksetSpec.properties.push({entity_type_selection: newEntityTypeSelection, property: ['']});
            },

            updateLogicBoxTypes(conditions) {
                if (conditions.hasOwnProperty('type')) {
                    if (this.useFuzzyLogic) {
                        if (conditions.type === 'AND')
                            conditions.type = 'MINIMUM_T_NORM';
                        if (conditions.type === 'OR')
                            conditions.type = 'MAXIMUM_T_CONORM';
                    }
                    else {
                        if (this.tNorms.includes(conditions.type))
                            conditions.type = 'AND';
                        if (this.tConorms.includes(conditions.type))
                            conditions.type = 'OR';
                    }
                }

                if (conditions.hasOwnProperty('conditions'))
                    conditions.conditions.forEach(condition => this.updateLogicBoxTypes(condition));
            },

            async runLinkset(force = false) {
                if (this.validateLinkset()) {
                    const data = await this.$root.runLinkset(this.linksetSpec.id, force);
                    if (data.result === 'exists' && confirm('This linkset already exists.\nDo you want to overwrite it with the current configuration?'))
                        await this.runLinkset(true);

                    EventBus.$emit('refresh');
                }
            },

            async runClustering() {
                const associationFile = this.association !== '' ? this.association : null;
                await this.$root.runClustering('linkset', this.linksetSpec.id, associationFile);
                EventBus.$emit('refresh');
            },

            async killLinkset() {
                await this.$root.killLinkset(this.linksetSpec.id);
                EventBus.$emit('refresh');
            },

            async killClustering() {
                await this.$root.killClustering('linkset', this.linksetSpec.id);
                EventBus.$emit('refresh');
            },
        },
        mounted() {
            if (this.linksetSpec.sources.length < 1)
                this.addEntityTypeSelection('sources');

            if (this.linksetSpec.targets.length < 1)
                this.addEntityTypeSelection('targets');

            this.useFuzzyLogic = !['AND', 'OR'].includes(this.linksetSpec.methods.type);
        },
        watch: {
            useFuzzyLogic() {
                this.updateLogicBoxTypes(this.linksetSpec.methods);
            },
        },
    };
</script>
