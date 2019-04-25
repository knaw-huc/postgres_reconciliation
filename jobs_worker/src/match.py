from conditions import Conditions
from helpers import hash_string, PropertyField
import json
from psycopg2 import sql as psycopg_sql


class Match:
    def __init__(self, data):
        for condition in data['conditions']['items']:
            condition['hash'] = hash_string(json.dumps(condition))

            resources_keys = ['sources']
            if 'targets' in condition:
                resources_keys.append('targets')
            for resources_key in resources_keys:
                for index, resource in condition[resources_key].items():
                    for property_field in resource:
                        condition[resources_key][index] = PropertyField(property_field)

        self.__data = data

    @property
    def conditions(self):
        return Conditions(self.__data['conditions'])

    @property
    def conditions_sql(self):
        return self.conditions.conditions_sql

    @property
    def is_association(self):
        return self.__data.get('is_association', False)

    @property
    def index_sql(self):
        index_sqls = []
        for template in self.conditions.index_templates:
            if 'template' not in template:
                continue
            if 'before_index' in template and template['before_index']:
                index_sqls.append(psycopg_sql.SQL(template['before_index']))

            for condition in self.conditions.conditions_list:
                resources = condition.targets if len(condition.targets) > 0 else condition.sources
                for resource_name, property_field in resources.items():
                    resource_field_name = template['field_name'][2::]\
                        if template['field_name'].startswith('__')\
                        else property_field.hash

                    template_sql = psycopg_sql.SQL(template['template']).format(
                        target=psycopg_sql.Identifier(resource_field_name))

                    index_sqls.append(psycopg_sql.SQL('CREATE INDEX ON {} USING {};').format(
                        psycopg_sql.Identifier(hash_string(resource_name)), template_sql))

        return psycopg_sql.SQL('\n').join(index_sqls)

    @property
    def matches_dependencies(self):
        dependencies = []

        for condition in self.conditions.conditions_list:
            if condition.function_name == 'IS_IN_SET':
                dependencies += condition.parameters

        return dependencies

    @property
    def materialize(self):
        return self.meta.get('materialize', True)

    @property
    def meta(self):
        return self.__data.get('meta', {})

    @property
    def name(self):
        return hash_string(self.name_original)

    @property
    def name_original(self):
        return self.__data['label']

    @property
    def resources(self):
        return self.sources + self.targets

    @property
    def similarity_fields_sql(self):
        fields = []

        for condition in self.conditions.conditions_list:
            if condition.similarity_sql:
                # Add source and target values
                field_name = psycopg_sql.Identifier(condition.field_name)
                fields.append(psycopg_sql.SQL('source.{field_name} AS {source_field_name}').format(
                    field_name=field_name,
                    source_field_name=psycopg_sql.Identifier(f'source_{condition.field_name}'),
                ))
                fields.append(psycopg_sql.SQL('target.{field_name} AS {target_field_name}').format(
                    field_name=field_name,
                    target_field_name=psycopg_sql.Identifier(f'target_{condition.field_name}'),
                ))

                # Add similarity field
                fields.append(psycopg_sql.SQL('{field} AS {field_name}')
                                 .format(
                                    field=condition.similarity_sql.format(field_name=field_name),
                                    field_name=psycopg_sql.Identifier(condition.field_name + '_similarity')
                ))

        return psycopg_sql.SQL(',\n       ').join(fields)

    @property
    def source_sql(self):
        return self.get_combined_resources_sql('sources')

    @property
    def target_sql(self):
        return self.get_combined_resources_sql('targets') if 'targets' in self.__data else self.source_sql

    @property
    def sources(self):
        return self.__data['sources']

    @property
    def targets(self):
        return self.__data['targets'] if 'targets' in self.__data else []

    def get_combined_resources_sql(self, resources_key):
        resources_properties = self.get_matching_fields(resources_key)

        resources_sql = []

        for resource_label, resource_properties in resources_properties.items():
            property_fields = []
            for property_label, resource_method_properties in resource_properties.items():
                for resource_property in resource_method_properties:
                    property_fields.append(psycopg_sql.SQL('{property_field} AS {field_name}')
                                           .format(
                                                property_field=psycopg_sql.Identifier(resource_property.hash),
                                                field_name=psycopg_sql.Identifier(property_label)))

            property_fields_sql = psycopg_sql.SQL(',\n           ').join(property_fields)

            resources_sql.append(psycopg_sql.SQL("""
    SELECT {collection} AS collection,
           uri,
           {matching_fields}
    FROM {resource_label}
""").format(
                collection=psycopg_sql.Literal(resource_label),
                matching_fields=property_fields_sql,
                resource_label=psycopg_sql.Identifier(resource_label)
            ))

        return psycopg_sql.SQL('    UNION ALL').join(resources_sql)

    def get_matching_fields(self, resources_keys=None):
        if not isinstance(resources_keys, list):
            resources_keys = ['sources', 'targets']

        # Regroup properties by resource instead of by method
        for resources_key in resources_keys:
            resources_properties = {hash_string(resource_name): {} for resource_name in getattr(self, resources_key)}

            for condition in self.conditions.conditions_list:
                for resource_label, resource_properties in getattr(condition, resources_key).items():
                    if condition.field_name not in resources_properties[hash_string(resource_label)]:
                        resources_properties[hash_string(resource_label)][condition.field_name] = []

                    resources_properties[hash_string(resource_label)][condition.field_name].append(resource_properties)

        return resources_properties

        # resources_properties = {
        #     'Resource label': {
        #         'value_n': [
        #             Property,
        #         ],
        #     },
        # }
