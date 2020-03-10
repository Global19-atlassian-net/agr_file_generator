import os
import time
import json
import logging

import upload

from py2neo import Node, Relationship

logger = logging.getLogger(name=__name__)


class GraphQLSchemaFileGenerator:

    empty_value_marker = '.'

    def __init__(self, entities, generated_files_folder, config_info):
        self.entities = entities
        self.config_info = config_info
        self.generated_files_folder = generated_files_folder


    def generate_file(self, upload_flag=False):
        filename = "graphql." + self.config_info.config['RELEASE_VERSION'] + ".schema"
        filepath = os.path.join(self.generated_files_folder, filename)
        nodes = dict()
        relationships_in = dict()
        relationships_out = dict()
        for record in self.entities:
            for node in record['nodes']:
                raw_node = dict(node)
                if len(raw_node['name']):
                    nodes[raw_node['name']] = {'count': raw_node['count'],
                                               'properties': raw_node['properties']}

            for relationship in record['relationships']:
                print(relationship)
                relationship_properties = record['relationships'][relationship]['properties']
                print(relationship_properties)

                #print(dict(relationship)['type'])
                #print(relationship.start_node())
                exit()
         
        with open(filepath, "w") as f:
            for node_type in nodes:
                f.write("type " + node_type + " {\n")
                for prop_type in nodes[node_type]['properties']:
                    print(prop_type['type'])
                    print(prop_type['property'])
                    f.write("    " + prop_type['property'] + ": " + prop_type['type'] + "\n")
                f.write("}\n\n")

        if upload_flag:
            logger.info("Submitting GraphQL Schema to FMS")
            process_name = "1"
            upload.upload_process(process_name, filename, self.generated_files_folder, 'GRAPHQL-SCHEMA', self.config_info.config['RELEASE_VERSION'], self.config_info)
