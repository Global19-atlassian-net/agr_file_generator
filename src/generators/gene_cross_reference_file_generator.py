import os
import logging
import csv
from time import gmtime, strftime

from upload import upload

logger = logging.getLogger(name=__name__)


class GeneCrossReferenceFileGenerator:

    file_header_template = """#########################################################################
#
# Gene Cross Reference
# Source: Alliance of Genome Resources (Alliance)
# Datebase Version: {databaseVersion}
# Date: {datetimeNow}
#
#########################################################################
"""

    def __init__(self, gene_cross_references, generated_files_folder, config_info):
        self.gene_cross_references = gene_cross_references
        self.config_info = config_info
        self.generated_files_folder = generated_files_folder

    @classmethod
    def _generate_header(cls, config_info):
        return cls.file_header_template.format(datetimeNow=strftime("%Y-%m-%d %H:%M:%S", gmtime()),
                                               databaseVersion=config_info.config['RELEASE_VERSION'])

    def generate_file(self, upload_flag=False):
        filename = 'agr-gene-cross-references-' + self.config_info.config['RELEASE_VERSION'] + '.tsv'
        output_filepath = os.path.join(self.generated_files_folder, filename)
        gene_cross_reference_file = open(output_filepath,'w')
        gene_cross_reference_file.write(self._generate_header(self.config_info))

        columns = ['GeneID',
                   'GlobalCrossReferenceID',
                   'CrossReferenceCompleteURL',
                   'ResourceDescriptorPage']

        tsv_writer = csv.DictWriter(gene_cross_reference_file, delimiter='\t', fieldnames=columns, lineterminator="\n")
        tsv_writer.writeheader()
        for data in self.gene_cross_references:
            row = dict(zip(columns, [None] * len(columns)))
            row['GeneID'] = data['GeneID']
            row['GlobalCrossReferenceID'] = data['GlobalCrossReferenceID']
            row['CrossReferenceCompleteURL'] = data['CrossReferenceCompleteURL']
            row['ResourceDescriptorPage'] = data['ResourceDescriptorPage']
            tsv_writer.writerows([row])
        gene_cross_reference_file.close()
        if upload_flag:
            logger.info("Submitting to FMS")
            process_name = "1"
            upload.upload_process(process_name, filename, self.generated_files_folder, 'GENECROSSREFERENCE',
                                  'COMBINED', self.config_info)