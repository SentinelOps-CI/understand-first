import zipfile
def create_pack(lens: str, tour: str, contracts: str, output_zip: str):
    with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(lens, arcname='lens.json')
        z.write(tour, arcname='tour.md')
        z.write(contracts, arcname='contracts.yaml')
