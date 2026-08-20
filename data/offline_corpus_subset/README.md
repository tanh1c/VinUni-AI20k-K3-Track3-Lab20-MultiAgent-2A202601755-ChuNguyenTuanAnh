# Official Corpus Benchmark Subset

Topics are stored as deterministic gzip bytes encoded into ordered ASCII base64 chunks. The loader concatenates chunks, base64-decodes, decompresses, and validates SHA-256 of the byte-exact original topic JSON.
