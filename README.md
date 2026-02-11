# mRemoteNGToMacOS
Py script to convert an mRemoteNG XML file to usable RDP files for macOS

Usage:

python3 mrng_to_rdp.py connections.xml output_dir \
  --default-gateway gateway.example.com

  Add the -p option to specify credentials to be added to the macOS Keychain.