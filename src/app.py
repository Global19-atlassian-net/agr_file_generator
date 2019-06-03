import os

from vcf_file_generator import VcfFileGenerator


host = os.environ.get('NEO4J_HOST', 'localhost')

port = int(os.environ.get('NEO4J_PORT', 7687))

alliance_db_version = os.environ.get('ALLIANCE_DATABASE_VERSION', 'test')

uri = "bolt://" + host + ":" + str(port)

if __name__ == '__main__':
    generated_files_folder = "generated_files"
    gvf = VcfFileGenerator(uri, generated_files_folder, alliance_db_version)
    gvf.generateFiles()
