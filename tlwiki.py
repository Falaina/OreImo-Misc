# Compliation date: 29/01/2011
import fileinput, re, os, os.path, sys
import http.cookiejar, urllib.request, urllib.parse
import mimetypes, random
import configparser

debug = False
count = 0
config = configparser.ConfigParser()
config.read(os.path.join(os.path.dirname(sys.argv[0]), 'config.ini'))

category = False
editsummary = False

# usoda's funbox
chars = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
def enc_multipart(fields):
    """
    <+usoda> TinFoil: Also fields should be a sequence of (name, value) or (name, value, filename) tuples
    <+usoda> TinFoil: The values are supposed to be bytes while the field names and filenames are supposed to be strings
    """
    boundary = bytes(random.choice(chars) for i in range(20))
    lines = []
    for field in fields:
        try:
            name, value = field
            filename = ''
        except ValueError:
            name, value, filename = field
        lines.append(b'--' + boundary)
        lines.append(bytes('Content-Disposition: form-data; name="%s"' % name, 'utf8'))
        if filename:
            lines[-1] += bytes('; filename="%s"' % filename, 'utf8')
            lines.append(bytes('Content-Type: ' + (mimetypes.guess_type(filename)[0] or 'application/octet-stream'), 'utf8'))
        lines.extend([b'', value])
    lines.extend([b'--' + boundary + b'--', b''])
    return 'multipart/form-data; boundary="%s"' % boundary.decode('ascii'), b'\r\n'.join(lines)

# Step 1: Log in
# xml.parsers.expat is a tad overcomplicated for our purposes
username = config.get('User Settings', 'username')
password = config.get('User Settings', 'password')
file_codepage = config.get('File Settings', 'codepage')
print('Using username:', username)
print('Using codepage:', file_codepage)

if config.has_option('Upload Settings', 'category'):
    category = config.get('Upload Settings', 'category').replace(' ', '_')
    print('Using category:', category)
if config.has_option('Upload Settings', 'editsummary'):
    editsummary = config.get('Upload Settings', 'editsummary')
    print('Using Edit Summary:', editsummary)

login = [('action', 'login'),
        ('lgname', username), ('lgpassword', password), ('format', 'xml')]
logindata = urllib.parse.urlencode(login)

cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler(), 
                                        urllib.request.HTTPCookieProcessor(cookies))
login_pg = opener.open('http://notcliche.com/rinjinbu/api.php?', bytes(logindata, 'ascii'))

# Get token and sessionid, add to confirmdata.
confirmation = login_pg.read()
if debug == True:
    open('confirm.xml', 'wb').write(confirmation)

token = re.search('(?<=token=")[A-Z-a-z0-9]+(?=")', confirmation.decode()).group()
if debug == True:
    print('Token: ', token)
sessionid = re.search('(?<=sessionid=")[A-Z-a-z0-9]+(?=")', confirmation.decode()).group()
login.extend([('lgtoken', token), ('sessionid', sessionid)])
confirmdata = urllib.parse.urlencode(login)

# Some error control here
if token == None:
    input('Cannot log in, for whatever reason. Press enter to exit. :(')
    sys.exit()

# Confirm token and login!
opener.open('http://notcliche.com/rinjinbu/api.php?', bytes(confirmdata, 'ascii'))

# Todo: Save the cookie to a file to use for 30 days =3=

# -------------------------------
# Step 1a: Get session edit token
etokdata = urllib.parse.urlencode([('action', 'query'), 
    ('prop', 'info'), ('intoken', 'edit'), ('titles', 'Boku_Shoujo'), ('format', 'xml')])
etok_pg = opener.open('http://notcliche.com/rinjinbu/api.php?', bytes(etokdata, 'ascii'))

etoken = re.search('(?<=edittoken=")[A-Z-a-z0-9]*\\+\\\\(?=")', etok_pg.read().decode()).group()
if debug == True:
    open('etok.xml', 'wb').write(etok_pg.read())
    print('Edit token:', etoken)

# -------------------------------
# Step 1b: Check if we have bot status
# Yeah, I'm a weeaboo. What about it.
botan = urllib.parse.urlencode([('action', 'query'), 
        ('meta', 'userinfo'), ('uiprop', 'groups'), ('titles', 'Boku_Shoujo'), ('format', 'xml')])
botstat = opener.open('http://notcliche.com/rinjinbu/api.php?', bytes(botan, 'ascii'))

# May or may not find bot status.
# -------------------------------
# Step 2: Get some fscking files
flist = []
for arg in sys.argv[1:]:
    if os.path.isdir(arg):
        for root, dirs, files in os.walk(arg):
            for piss in files:
                flist.append(os.path.join(root, piss))
    elif os.path.isfile(arg):
        flist.append(arg)

imagery = ['jpeg', 'jpg', 'png', 'bmp', 'gif', 'tiff', 'raw', 'svg']
image = False
# -------------------------------
# Step 3: Upload w/ LIVE STATUS UPDATES
# print('upfile: ', upfile)
for upfile in flist:
    for type in imagery:
        if type in upfile:
            image = True
            break
        else:
            image = False
    # For non-images (text)
    if not image:
        filename = os.path.basename(upfile)
        print('Uploading file', count + 1, '...')
        editbox = open(upfile, encoding=file_codepage).read()
        if category:
            if not '<pre>' in editbox:
                editbox = '<pre> {0} \n</pre>\n\n[[Category:{1}]]'.format(editbox, category)
            editparams = [('action', 'edit'), ('title', category + ':' + filename), 
                        ('text', editbox), ('token', etoken)]
        else:
            if not '<pre>' in editbox:
                editbox = '<pre>' + open(upfile, encoding=file_codepage).read() + '\n</pre>'
            editparams = [('action', 'edit'), ('title', filename), 
                        ('text', editbox), ('token', etoken)]
        if editsummary:
            editparams.append(('summary', editsummary))
        try:
            opener.open('http://notcliche.com/rinjinbu/api.php?&bot&', bytes(urllib.parse.urlencode(editparams), 'ascii'))
        except:
            print('Error! File could not be uploaded. Please check your network connection or whatever.')
            input('This script has commited suicide in face of such a failure.')
            raise
            sys.exit()
        else:
            count += 1
            print('{0} successfully uploaded ({1})'.format(filename, count))
            editparams = []
    # For images
    elif image:
        filename = os.path.basename(upfile)
        contents = open(upfile, 'rb').read()
        if category:
            imgparams = [('action', b'upload'),
                        ('filename', bytes(category[:3] + '_' + filename, encoding = 'utf8')), 
                        ('token', bytes(etoken, encoding = 'utf8')), ('file', contents, filename)]
        else:
            imgparams = [('action', b'upload'),
                        ('filename', bytes(filename, encoding = 'utf8')), 
                        ('token', bytes(etoken, encoding = 'utf8')), ('file', contents, filename)]
        if editsummary:
            imgparams.append(('comment', bytes(editsummary, encoding = 'utf8')))
        ctype, imgdata = enc_multipart(imgparams)
        imageup = urllib.request.Request('http://notcliche.com/rinjinbu/api.php?&bot',
                                        imgdata, {'Content-Type': ctype})
        try:
            opener.open(imageup)
            print('{0} successfully uploaded ({1})'.format(filename, count))
            count = count + 1
        except:
            print('Error! Image could not be uploaded. Please check your network connection or whatever.')
            input('This script has commited suicide in face of such a failure.')
            sys.exit()
print(count, 'total files uploaded.')
input('Press enter to quit.')
