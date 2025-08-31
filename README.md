# parser-products
A parser for collecting characteristics and photos of products

The parser was used to collect data from a specific site, it is not a universal project. The file parser2.py collects the Description and Attributes of the product in a format suitable for further import into WordPress. 
parser_photo_final.py downloads the photo and translates the name into the Latin alphabet suitable for downloading, after which it updates the csv file created by the previous file, adding the names of the corresponding photo products to the "Images" column.

So I recommend running the scripts in this order if anyone ever needs them.
