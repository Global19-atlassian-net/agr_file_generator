
import logging
import os
import time

import click
import coloredlogs
import requests
import urllib3
from common import ContextInfo
from data_source import DataSource
from generators import (daf_file_generator,
                        db_summary_file_generator,
                        expression_file_generator,
                        gene_cross_reference_file_generator,
                        orthology_file_generator,
                        vcf_file_generator,
                        graphql_schema_file_generator,
                        uniprot_cross_reference_generator)


port = int(os.environ.get('NEO4J_PORT', 7687))
alliance_db_version = os.environ.get('ALLIANCE_RELEASE')
NEO4J_HOST = os.environ.get('NEO4J_HOST')

context_info = ContextInfo()
debug_level = logging.DEBUG if context_info.config["DEBUG"] else logging.INFO
neo_debug_level = logging.DEBUG if context_info.config["NEO_DEBUG"] else logging.INFO

coloredlogs.install(level=debug_level,
                    fmt='%(asctime)s %(levelname)s: %(name)s:%(lineno)d: %(message)s',
                    field_styles={
                            'asctime': {'color': 'green'},
                            'hostname': {'color': 'magenta'},
                            'levelname': {'color': 'white', 'bold': True},
                            'name': {'color': 'blue'},
                            'programname': {'color': 'cyan'}
                    })

logging.getLogger("urllib3").setLevel(debug_level)
logging.getLogger("neobolt").setLevel(neo_debug_level)
logger = logging.getLogger(__name__)

taxon_id_fms_subtype_map = {"NCBI:txid10116": "RGD",
                            "NCBI:txid9606": "HUMAN",
                            "NCBI:txid7227": "FB",
                            "NCBI:txid6239": "WB",
                            "NCBI:txid7955": "ZFIN",
                            "NCBI:txid10090": "MGI",
                            "NCBI:txid559292": "SGD"}

@click.command()
@click.option('--vcf', is_flag=True, help='Generates VCF files')
@click.option('--orthology', is_flag=True, help='Generates orthology files')
@click.option('--disease', is_flag=True, help='Generates DAF files')
@click.option('--expression', is_flag=True, help='Generates expression files')
@click.option('--graphql-schema', is_flag=True, help='Generates schema file GraphQL')
@click.option('--db-summary', is_flag=True, help='Generates summary of database contents')
@click.option('--gene-cross-reference', is_flag=True, help='Generates a file of cross references for gene objects')
@click.option('--all-filetypes', is_flag=True, help='Generates all filetypes')
@click.option('--tab', is_flag=True, help='Generates tab delimited files with VCF info columns contents')
@click.option('--uniprot', is_flag=True, help='Generates a file of gene and uniprot cross references')
@click.option('--upload', is_flag=True, help='Submits generated files to File Management System (FMS)')
def main(vcf,
         orthology,
         disease,
         expression,
         graphql_schema,
         db_summary,
         gene_cross_reference,
         all_filetypes,
         upload,
         tab,
         uniprot,
         generated_files_folder=os.path.abspath(os.path.join(os.getcwd(), os.pardir)) + '/output',
         input_folder=os.path.abspath(os.path.join(os.getcwd(), os.pardir )) + '/input',
         fasta_sequences_folder='sequences',
         skip_chromosomes={'Unmapped_Scaffold_8_D1580_D1567'}):

    start_time = time.time()
    click.echo(start_time)

    if not os.path.exists(generated_files_folder):
        os.makedirs(generated_files_folder)

    click.echo('INFO:\tFiles output: ' + generated_files_folder)
    if vcf is True or all_filetypes is True:
        if not tab:
            click.echo('INFO:\tGenerating VCF files')
        else:
            click.echo('INFO:\tGenerating TAB delimited files')
        generate_vcf_files(generated_files_folder, fasta_sequences_folder, skip_chromosomes, context_info, upload, tab)
    if orthology is True or all_filetypes is True:
        click.echo('INFO:\tGenerating Orthology file')
        generate_orthology_file(generated_files_folder, context_info, upload)
    if disease is True or all_filetypes is True:
        click.echo('INFO:\tGenerating Disease files')
        generate_daf_file(generated_files_folder, context_info, taxon_id_fms_subtype_map, upload)
    if expression is True or all_filetypes is True:
        click.echo('INFO:\tGenerating Expression files')
        generate_expression_file(generated_files_folder, context_info, taxon_id_fms_subtype_map, upload)
    if graphql_schema is True:
        click.echo('INFO:\tGenerating GraphQL Schema file')
        generate_graphql_schema_file(generated_files_folder, context_info, upload)
    if db_summary is True or all_filetypes is True:
        click.echo('INFO:\tGenerating DB summary file')
        generate_db_summary_file(generated_files_folder, context_info, upload)
    if gene_cross_reference is True or all_filetypes is True:
        click.echo('INFO:\tGenerating Gene Cross Reference file')
        generate_gene_cross_reference_file(generated_files_folder, context_info, upload)
    if uniprot is True or all_filetypes is True:
        click.echo('INFO:\tGenerating UNIPROT cross reference file')
        generate_uniprot_cross_reference(generated_files_folder, input_folder, context_info, upload)

    end_time = time.time()
    elapsed_time = end_time - start_time
    click.echo('File Generator finished. Elapsed time: %s' % time.strftime("%H:%M:%S", time.gmtime(elapsed_time)))


def get_neo_uri(context_info):
    if context_info.config['NEO4J_HOST']:
        uri = "bolt://" + context_info.config['NEO4J_HOST'] + ":" + str(port)
        logger.info("Using db URI: {}".format(uri))
        return uri
    else:
        logger.error("Need to set NEO4J_HOST env variable")
        exit()


def generate_vcf_files(generated_files_folder, fasta_sequences_folder, skip_chromosomes, context_info, upload_flag, tab_flag):
    os.makedirs(generated_files_folder, exist_ok=True)
    os.makedirs(fasta_sequences_folder, exist_ok=True)
    variants_query = """MATCH (s:Species)-[:FROM_SPECIES]-(a:Allele)-[:VARIATION]-(v:Variant)-[l:LOCATED_ON]-(c:Chromosome),
                              (v:Variant)-[:VARIATION_TYPE]-(st:SOTerm),
                              (v:Variant)-[:ASSOCIATION]-(p:GenomicLocation)
                     OPTIONAL MATCH (a:Allele)-[:IS_ALLELE_OF]-(g:Gene)
                     OPTIONAL MATCH (v:Variant)-[:ASSOCIATION]-(m:GeneLevelConsequence)
                     RETURN c.primaryKey AS chromosome,
                            v.globalId AS globalId,
                            right(v.paddingLeft,1) AS paddingLeft,
                            v.genomicReferenceSequence AS genomicReferenceSequence,
                            v.genomicVariantSequence AS genomicVariantSequence,
                            v.hgvsNomenclature AS hgvsNomenclature,
                            v.dataProvider AS dataProvider,
                            a.symbol AS symbol,
                            a.symbolText as symbolText,
                            p.assembly AS assembly,
                            collect(a.primaryKey) AS alleles,
                            collect(g.primaryKey) AS geneSymbol,
                            CASE WHEN g IS NOT NULL THEN collect(g.primaryKey) ELSE [] END AS alleleOfGenes,
                            CASE WHEN m IS NOT NULL THEN collect(m.geneLevelConsequence) ELSE [] END AS geneLevelConsequence,
                            CASE WHEN m IS NOT NULL THEN collect(m.impact) ELSE '' END AS impact,
                            p.start AS start,
                            p.end AS end,
                            s.name AS species,
                            st.nameKey AS soTerm
                     """
    data_source = DataSource(get_neo_uri(context_info), variants_query)
    gvf = vcf_file_generator.VcfFileGenerator(data_source,
                                              generated_files_folder,
                                              context_info)
    gvf.generate_files(skip_chromosomes=skip_chromosomes, upload_flag=upload_flag, tab_flag=tab_flag)


def generate_orthology_file(generated_files_folder, context_info, upload_flag):
    orthology_query = '''MATCH (species1)<-[sa:FROM_SPECIES]-(gene1:Gene)-[o:ORTHOLOGOUS]->(gene2:Gene)-[sa2:FROM_SPECIES]->(species2:Species)
                       WHERE o.strictFilter
                       OPTIONAL MATCH (algorithm:OrthoAlgorithm)-[m:MATCHED]-(ogj:OrthologyGeneJoin)-[association:ASSOCIATION]-(gene1)
                       WHERE ogj.primaryKey = o.primaryKey
                       OPTIONAL MATCH (algorithm2:OrthoAlgorithm)-[m2:NOT_MATCHED]-(ogj2:OrthologyGeneJoin)-[ASSOCIATION]-(gene1)
                       WHERE ogj2.primaryKey = o.primaryKey
                       RETURN gene1.primaryKey AS gene1ID,
                              gene1.symbol AS gene1Symbol,
                              gene2.primaryKey AS gene2ID,
                              gene2.symbol AS gene2Symbol,
                              collect(DISTINCT algorithm.name) as Algorithms,
                              count(DISTINCT algorithm.name) AS numAlgorithmMatch,
                              count(DISTINCT algorithm2.name) AS numAlgorithmNotMatched,
                              toString(o.isBestScore) AS best,
                              toString(o.isBestRevScore) AS bestRev,
                              species1.primaryKey AS species1TaxonID,
                              species1.name AS species1Name,
                              species2.primaryKey AS species2TaxonID,
                              species2.name AS species2Name'''
    data_source = DataSource(get_neo_uri(context_info), orthology_query)
    of = orthology_file_generator.OrthologyFileGenerator(data_source,
                                                         generated_files_folder,
                                                         context_info)
    of.generate_file(upload_flag=upload_flag)


def generate_daf_file(generated_files_folder, context_info, taxon_id_fms_subtype_map, upload_flag):
    daf_query = '''MATCH (dej:Association:DiseaseEntityJoin)-[:ASSOCIATION]-(object)-[da:IS_MARKER_FOR|IS_IMPLICATED_IN|IMPLICATED_VIA_ORTHOLOGY|BIOMARKER_VIA_ORTHOLOGY]->(disease:DOTerm)
                   WHERE (object:Gene OR object:Allele)
                   AND da.uuid = dej.primaryKey
                   MATCH (object)-[FROM_SPECIES]->(species:Species)
                   OPTIONAL MATCH (ec:Ontology:ECOTerm)-[:ASSOCIATION]-(:PublicationJoin)-[:EVIDENCE]-(dej:Association:DiseaseEntityJoin)
                   OPTIONAL MATCH (p:Publication)-[:ASSOCIATION]-(:PublicationJoin)-[:EVIDENCE]-(dej:Association:DiseaseEntityJoin)
                   OPTIONAL MATCH (dej)-[o:FROM_ORTHOLOGOUS_GENE]-(oGene:Gene)
                   WHERE o.strictFilter AND (ec.primaryKey = "ECO:0000250" OR ec.primaryKey = "ECO:0000266") // ISS and ISO respectively
                   //OPTIONAL MATCH (object)-[IS_ALLELE_OF]->(gene:Gene)
                   RETURN  object.taxonId AS taxonId,
                           species.name AS speciesName,
                           collect(DISTINCT oGene.primaryKey) AS withOrthologs,
                           labels(object) AS objectType,
                           object.primaryKey AS dbObjectID,
                           object.symbol AS dbObjectSymbol,
                           p.pubMedId AS pubMedID,
                           p.pubModId As pubModID,
                           type(da) AS associationType,
                           //collect(DISTINCT gene.primaryKey) AS inferredGeneAssociation,
                           disease.doId AS DOID,
                           disease.name as DOname,
                           ec.primaryKey AS evidenceCode,
                           dej.dateAssigned AS dateAssigned,
                           da.dataProvider AS dataProvider'''
    data_source = DataSource(get_neo_uri(context_info), daf_query)
    daf = daf_file_generator.DafFileGenerator(data_source,
                                              generated_files_folder,
                                              context_info,
                                              taxon_id_fms_subtype_map)
    daf.generate_file(upload_flag=upload_flag)


def generate_expression_file(generated_files_folder, context_info, taxon_id_fms_subtype_map, upload_flag):
    expression_query = '''MATCH (speciesObj:Species)<-[:FROM_SPECIES]-(geneObj:Gene)-[:ASSOCIATION]->(begej:BioEntityGeneExpressionJoin)--(term)
                          WITH {primaryKey: speciesObj.primaryKey, name: speciesObj.name} AS species,
                               {primaryKey: geneObj.primaryKey, symbol: geneObj.symbol} AS  gene,
                               begej,
                               COLLECT(term) AS terms
                          MATCH (begej:BioEntityGeneExpressionJoin)<-[:ASSOCIATION]-(exp:ExpressionBioEntity)-[a:ANATOMICAL_STRUCTURE|CELLULAR_COMPONENT|ANATOMICAL_SUB_SUBSTRUCTURE|CELLULAR_COMPONENT_QUALIFIER|ANATOMICAL_SUB_STRUCTURE_QUALIFIER|ANATOMICAL_STRUCTURE_QUALIFIER]->(ontology:Ontology)
                          //WHERE gene.primaryKey = 'ZFIN:ZDB-GENE-110411-206'
                          RETURN species, gene, terms, begej.primaryKey as begejId, exp.whereExpressedStatement as location,
                                                       COLLECT({edge: type(a),
                                                                primaryKey: ontology.primaryKey,
                                                                name: ontology.name}) as ontologyPaths'''
    data_source = DataSource(get_neo_uri(context_info), expression_query)
    expression = expression_file_generator.ExpressionFileGenerator(data_source,
                                                                   generated_files_folder,
                                                                   context_info,
                                                                   taxon_id_fms_subtype_map)
    expression.generate_file(upload_flag=upload_flag)


def generate_graphql_schema_file(generated_files_folder, context_info, upload_flag):
    schema_query = '''CALL apoc.meta.data() YIELD label, property, type, elementType
                      WHERE elementType <> 'relationship'
                            AND type <> 'RELATIONSHIP'
                      WITH label, collect({property: property, type: type}) AS properties
                      WITH apoc.map.fromLists(collect(label), collect(properties)) AS properties_map

                      CALL apoc.meta.graph() YIELD nodes, relationships
                      UNWIND nodes AS n
                      WITH n, apoc.text.join(apoc.node.labels(n), '-') AS label, properties_map, relationships

                      CALL apoc.create.setProperty(n, 'properties', properties_map[label]) YIELD node

                      RETURN collect(node) AS nodes, relationships'''
    data_source = DataSource(get_neo_uri(context_info), schema_query)
    graphql_schema = graphql_schema_file_generator.GraphQLSchemaFileGenerator(data_source,
                                                                        generated_files_folder,
                                                                        context_info)
    graphql_schema.generate_file(upload_flag=upload_flag)

def generate_db_summary_file(generated_files_folder, context_info, upload_flag):
    db_summary_query = '''MATCH (entity)
                          WITH labels(entity) AS entityTypes
                          RETURN count(entityTypes) AS frequency,
                          entityTypes'''
    data_source = DataSource(get_neo_uri(context_info), db_summary_query)
    db_summary = db_summary_file_generator.DbSummaryFileGenerator(data_source,
                                                                  generated_files_folder,
                                                                  context_info)
    db_summary.generate_file(upload_flag=upload_flag)


def generate_gene_cross_reference_file(generated_files_folder, context_info, upload_flag):
    gene_cross_reference_query = '''MATCH (g:Gene)--(cr:CrossReference)
                          RETURN g.primaryKey as GeneID, 
                                 cr.globalCrossRefId as GlobalCrossReferenceID, 
                                 cr.crossRefCompleteUrl as CrossReferenceCompleteURL, 
                                 cr.page as ResourceDescriptorPage,
                                 g.taxonId as TaxonID'''
    data_source = DataSource(get_neo_uri(context_info), gene_cross_reference_query)
    gene_cross_reference = gene_cross_reference_file_generator.GeneCrossReferenceFileGenerator(data_source,
                                                                  generated_files_folder,
                                                                  context_info)
    gene_cross_reference.generate_file(upload_flag=upload_flag)

def generate_uniprot_cross_reference(generated_files_folder, input_folder, context_info, upload_flag):
    uniprot_cross_reference_query = '''MATCH (g:Gene)--(cr:CrossReference)
                                WHERE cr.prefix = "UniProtKB"
                                RETURN g.primaryKey as GeneID, 
                                    cr.globalCrossRefId as GlobalCrossReferenceID'''
    data_source = DataSource(get_neo_uri(context_info), uniprot_cross_reference_query)
    ucf = uniprot_cross_reference_generator.UniProtGenerator(data_source, context_info, generated_files_folder)
    ucf.generate_file(upload_flag=upload_flag)


if __name__ == '__main__':
    main()
