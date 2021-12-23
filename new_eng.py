import cx_Oracle
import json
from flask.wrappers import Response
import jwt
import time
import datetime
from functools import wraps
from flask import Flask, jsonify, request, make_response
from flask_restful import Resource, Api
from flask_httpauth import HTTPBasicAuth
from datetime import datetime, timedelta
import requests
from string import Template
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from pdfgen import generateDnPdf, generateShedPdf

app = Flask(__name__)
app.config['SECRET_KEY'] = "XXXXXXXXX"
api = Api(app)
auth = HTTPBasicAuth()

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.args.get('token') 
        if not token:
            return jsonify({'message' : 'Token is missing!'}), 403
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'])
        except:
            return jsonify({'message' : 'Token is invalid!'}), 403
        
        return f(*args, **kwargs)
    return decorated

@app.route('/login')  
def login():
    auth = request.authorization
    if auth and auth.username == 'admin' and auth.password == 'Passwd1234':       
        token = jwt.encode({'user' : auth.username, 'exp' : datetime.utcnow() + timedelta(minutes=30)}, app.config['SECRET_KEY'])
        return jsonify({'token' : token.decode('UTF-8')})
    return make_response('Could not verify!', 401, {'WWW-Authenticate' : 'Basic realm="Login Required"'})

def fire_post_request(url, data,timeout,headers):
    start_time = time.time()
    response=requests.post(url, data=data,timeout=timeout,headers=headers)
    end_time=time.time() - start_time
    return response

def clean(string_with_empty_lines):
    lines = string_with_empty_lines.split("\n")
    non_empty_lines = [line for line in lines if line.strip() != ""]
    string_without_empty_lines  = ""
    for line in non_empty_lines:
          string_without_empty_lines  += line 
    return string_without_empty_lines.lstrip()  

def egov(xCPR_NO,xType,xReg_NO,xReg_Type,xChassis):

    url = 'https://services.bahrain.bh/NGI_GDTVehicleInsurance/services/InsuranceUploadImpl?wsdl'

    messagetemplate=Template(r"""<Envelope xmlns="http://schemas.xmlsoap.org/soap/envelope/">
        <Body>
            <retrieveInsurancePolicy xmlns="http://ws.egov.cio.com.bh">
                <userCred xmlns="">
                    <passKey>$Pass</passKey>
                    <userID>insurance_user</userID>
                </userCred>
                <retrieveInsuranceDet xmlns="">
                    <ownerNumber>$CPR_NO</ownerNumber>
                    <ownerType>$Type</ownerType>
                    <vehRegistrationNumber>$Reg_NO</vehRegistrationNumber>
                    <vehRegistrationType>$Reg_Type</vehRegistrationType>
                    <chassisNumber>$Chassis</chassisNumber>
                </retrieveInsuranceDet>
            </retrieveInsurancePolicy>
        </Body>
    </Envelope>""")
    
    headers = {'SOAPAction':'https://services.bahrain.bh/NGI_GDTVehicleInsurance/services/InsuranceUploadImpl', 'Content-Type':'text/xml'}
    
    data = messagetemplate.substitute(Pass=   'insurance_password',
                                    CPR_NO=   xCPR_NO,
                                    Type=     xType,
                                    Reg_NO=   xReg_NO,
                                    Reg_Type= xReg_Type,
                                    Chassis=  xChassis)
                                    
    x = fire_post_request(url, data,60,headers)
    
    soup = BeautifulSoup(x.content, 'xml')
    ns = soup.find('insuranceDueDate')
    insuranceDueDate = ns.string.strip()

    try:
        expiry = int(insuranceDueDate)
    except:
        return 'Wrong Data', ''    # Wrong inserted data
   
    cdate = int((datetime.now()).strftime("%Y%m%d"))

    diff = cdate - expiry 
    if diff > 0:
        return 'Lapsed', insuranceDueDate    # Policy Lapsed
   
    return 'Ok', insuranceDueDate # Okay

def rsa_loading(RSA_Option):

    if int(RSA_Option) == 10006:   # Invita RSA only
        rsa = 1
    elif int(RSA_Option) == 20108: # Invita 8 days w SC
        rsa = 2
    elif int(RSA_Option) == 20110: # Invita 10 days w SC
        rsa = 5
    elif int(RSA_Option) == 20115: # Invita 15 days w SC
        rsa = 6
    elif int(RSA_Option) == 20208: # Invita 8 days w MC
        rsa = 7
    elif int(RSA_Option) == 20210: # Invita 10 days w MC
        rsa = 8
    elif int(RSA_Option) == 20215: # Invita 15 days w MC
        rsa = 9
    elif int(RSA_Option) == 20308: # Invita 8 days w LC
        rsa = 10
    elif int(RSA_Option) == 20310: # Invita 10 days w LC
        rsa = 11
    elif int(RSA_Option) == 20315: # Invita 15 days w LC
        rsa = 15    

    return rsa

def age_loading(xDriver_Age,xTariff,xBase_Prem):
    
    Driver_Age = int(xDriver_Age)
    Tariff =     int(xTariff)
    base_prem =  float(xBase_Prem)

    if Tariff == 0:
        if Driver_Age < 25:
            age_loading = base_prem * 0.25
        else:
            age_loading = 0    
    else:
        if Driver_Age < 23:
            age_loading = base_prem * 0.25
        else:
            age_loading = 0      
    
    return age_loading  

def sport_loading(xMake,xModel):

    makes = {'Acura':       ['RSX'],
            'Audi':         ['TT','Quatro'],
            'Alfa Romeo':   ['4C','8C','Giulia','Spider'],
            'Avanti':       ['0'],
            'Aston Martin': ['0'],
            'Bentley':      ['GT','Continental'],
            'BMW':          ['645 CI','645ci','650','440i','645','650 Ci','745','745 Li','745ia','750','750 Li','750IL','760','760 Ial',
                             '840 Ci','i8','Z1','Z3','Z4','Z8','Z 4','M1','M2','M3','M4','M5','M6','M7','M8'],
            'Cadillac':     ['Eldorado','XLR'],
            'Chevrolet':    ['Camaro','Corvette','Corvette C1','Corvette C6','Corvette C7','Corvette Z06','Impala','Monte Carlo','Lumina Ss',
                             'Impala SS','Caprice SS'],
            'Chrysler':     ['Cross Fire'],
            'Dodge':        ['Challenger','Challenger Hellcat','Challenger R/T','Challenger SRT8','Charger R/T','Charger Srt8','Cheyenne Sport',
                             'Viper'],
            'Ferrari':      ['0'],
            'Ford':         ['Cougar','GT40','Mustang','Probe','Thunder Bird','Thunderbird'],
            'Honda':        ['CRX','Prelude','S-2000'],
            'Hyundai':      ['Coupe','Scoupe'],
            'Jaguar':       ['Xj12he','Xj6.3.4','Xj6.4.2','XJ8','XJL','Xjs He','Xk','XK8','XKR'],
            'Lamborghini':  ['0'],
            'Lexus':        ['RC-F','Sc 400','Sc300','SC430'],
            'Lotus':        ['0'],
            'Maserati':     ['0'],
            'Mazda':        ['Mx3','Mx5','MX-5','Mx-6','Rx7','RX-8','Rx8 Sport'],
            'McLaren':      ['0'],
            'Mercedes':     ['55 Amg','AMG C36','AMG C43','AMG GTR','C 63','CL 55','Cl 600','CL65','CLK','CLK55','CLS 500','CLS 55','CLS 550',
                             'CLS 63','E 500','E 55','E 550','E 63 AMG','E400','E420','E450','E55','E63','G 55','G 55 AMG','G500','G63','G65',
                             'GL63 AMG','GLE 43 Coupe','GLE63','GLS 450','GLS 500','GLS 600','GT 43','GT50','ML 63','S 450','S 500','S 600',
                             'S 650','S 850 Coupe','S500L','S55','S560','S63','S63 AMG','SL 500','Sl 55','SL 55 AMG','SL 63 AMG','SL65 AMG',
                             'SLC 450','SLC 55 AMG','SLK','SLK 350','SLR','SLS AMG'],
            'Mitsubishi':   ['3000 Gt','Eclipse','Evolution','Lancer Evolution','Starion'],
            'Morgan':       ['0'],
            'Nissan':       ['Gt','GTR','NX','Z 24','Z370','Zx','Zx 280'],
            'Plymouth':     ['Prowler','Sport Fury'],
            'Pontiac':      ['GTO','Fire Bird','Grand Am','Trans Am'],
            'Porsche':      ['911','911 C2s','911 Turbo','911-C16','918 Spyder','928 GTS','Boxster S','Boxter','Carrera','Carrera C25',
                             'Carrera Coupe','Carrera S','Carrera S Cabrio','Cayenne GTS','Cayman','Cayman R','Cayman S','Gt','GT 2',
                             'GT2 RS','Gt3','Gt3rs','Macan GTS','S 928','Turbo','Turbo 911'],
            'Toyota':       ['Celica','MR2 Spyder','Supra','Supra Turbo','Yaris GR'],
            'Saab':         ['9000'],
            'Saleen':       ['0'],
            'Subaru':       ['Wrx Sti'],
            'Volvo':        ['c70','S 80'],
            'Volkswagon':   ['Gti','R32']}
    found = 0
    i=0
    while True:
        try:
            if str(list(makes.items())[i][0]) == xMake:
                models = list(makes.items())[i][1]
                for model in models:
                    if model == xModel:
                        found = 1
        except:
            break
        i = i + 1

    return found

def new_quote_tpl(xMake,xModel,xReg_Type,xEngine_CC,xSeats,xNCC):

    Make =          xMake
    Model =         xModel
    Reg_Type =      xReg_Type
    Engine_CC =     int(xEngine_CC)
    Seats =         int(xSeats)
    NCC =           int(xNCC)
        
    if ((Reg_Type == 'PUBLIC TRANS.') | (Reg_Type == 'PVT TRNS-PSGR') |(Reg_Type == 'PUB TRNS-PSG.') | (Reg_Type == 'TOURIST BUSSES') | (Reg_Type == 'CONTRACTORS')):
        seat_prem = int(Seats)*3
        if Engine_CC < 1401:
            base_prem = 167 + seat_prem
            min_prem = 154 + seat_prem
        elif Engine_CC < 2201:
            base_prem = 175 + seat_prem
            min_prem =  160 + seat_prem
        elif Engine_CC < 3651:
            base_prem = 189 + seat_prem
            min_prem =  171 + seat_prem
        elif Engine_CC > 3650:
            base_prem = 212 + seat_prem
            min_prem =  190 + seat_prem
    elif ((Reg_Type == 'PRIVATE') | (Reg_Type == 'DIPLOMATIC') | (Reg_Type == 'ROYAL COURT')):
        if Engine_CC < 1401:
            base_prem = 153
            min_prem = 142
        elif Engine_CC < 2201:
            base_prem = 159
            min_prem = 147
        elif Engine_CC < 3651:
            base_prem = 171
            min_prem = 157
        elif Engine_CC > 3650:
            base_prem = 183
            min_prem = 166
    elif (Reg_Type == 'MOTORCYCLE'):
        if Engine_CC < 251:
            base_prem = 155
            min_prem = 144
        elif Engine_CC < 401:
            base_prem = 170
            min_prem = 156
        elif Engine_CC < 751:
            base_prem = 195
            min_prem = 176
        elif Engine_CC > 750:
            base_prem = 250
            min_prem = 220
    elif ((Reg_Type == 'TAXI') | (Reg_Type == 'TAXI ON CALL')):
        if Engine_CC < 1401:
            base_prem = 193
            min_prem = 175
        elif Engine_CC < 2201:
            base_prem = 197
            min_prem = 178
        elif Engine_CC < 3651:
            base_prem = 203
            min_prem = 183
        elif Engine_CC > 3650:
            base_prem = 212
            min_prem = 190
    elif (Reg_Type == 'FOR HIRE'):
        if Engine_CC < 1401:
            base_prem = 272
            min_prem = 238
        elif Engine_CC < 2201:
            base_prem = 277
            min_prem = 242
        elif Engine_CC < 3651:
            base_prem = 283
            min_prem = 247
        elif Engine_CC > 3650:
            base_prem = 300    
            min_prem =  260  
    else:
        if Engine_CC < 1401:
            base_prem = 176
            min_prem = 161
        elif Engine_CC < 2201:
            base_prem = 185
            min_prem = 168
        elif Engine_CC < 3651:
            base_prem = 193
            min_prem = 174
        elif Engine_CC > 3650:
            base_prem = 225  
            min_prem =  200
   
    if int(sport_loading(Make,Model)) == 1: 
        base_prem = base_prem * 1.7
        min_prem = base_prem * 1.3

    if NCC == 0:
        base_prem = base_prem * 1.25
    elif NCC == 1:
        base_prem = base_prem * 0.95
    elif NCC == 2:
        base_prem = base_prem * 0.9
    elif NCC == 3:
        base_prem = base_prem * 0.85
    elif NCC == 4:
        base_prem = base_prem * 0.8       

    if base_prem < min_prem:
        base_prem = min_prem
    
    # returned base premium is exclusive of RSA and VAT
    return base_prem

def new_quote_comp(xMake,xModel,xReg_Type,xYOM,xNew,xSeats,xSI,xNCC):

    Make =          xMake
    Model =         xModel
    Reg_Type =      xReg_Type 
    YOM =           int((datetime.now()).strftime("%Y")) - int(xYOM)
    Seats =         int(xSeats)
    if int(xNew) == 0:
        SI =        int(xSI)
    else:
        SI =        int(xSI)
    NCC =           int(xNCC)
        
    if int(SI) > 40000:
        return 2 # High Value 
    
    if NCC == 0:
        if int(YOM) > 6:
            return 3 # Unable to cover due to high risk. Recommend TPL only
    
    # Comprehensive Standard
    if ((Reg_Type == 'PRIVATE') | (Reg_Type == 'DIPLOMATIC') | (Reg_Type == 'ROYAL COURT')):        
        if int(SI) < 15000:
            std_base = int(SI) * 0.023
        elif int(SI) < 40001:
            std_base = int(SI) * 0.020                   
        if Make == 'Mercedes':
            std_base = int(SI) * 0.020                    
        std_min = 130       
    elif ((Reg_Type == 'PVT TRNS-PSGR') |(Reg_Type == 'PUB TRNS-PSG.') | (Reg_Type == 'TOURIST BUSSES') | (Reg_Type == 'CONTRACTORS')):
        seat_prem = int(Seats)*3
        std_base = int(SI) * 0.029
        std_base = std_base + seat_prem
        std_min = 180 + seat_prem 
    else:
        std_base = int(SI) * 0.03
        std_min = 180 #160   

    if int(sport_loading(Make,Model)) == 1:
        std_base = int(SI) * 0.04
        std_min = 200 

     # Comprehensive Nil Depreciation
    if ((Reg_Type == 'PRIVATE') | (Reg_Type == 'DIPLOMATIC') | (Reg_Type == 'ROYAL COURT')):
        if ((YOM > 7) | (YOM < 4)):            
            nil_base = 0
            nil_min = 0
        else:
            if int(SI) < 15000:
                nil_base = int(SI) * 0.026
            elif int(SI) < 40001:
                nil_base = int(SI) * 0.023                               
            nil_min = 190 # 180     

            if int(sport_loading(Make,Model)) == 1:
                nil_base = int(SI) * 0.027
                nil_min = 380 #300             

    # Comprehensive Plus
    if ((Reg_Type == 'PRIVATE') | (Reg_Type == 'DIPLOMATIC') | (Reg_Type == 'ROYAL COURT')): 
        if ((YOM == 3) | (YOM == 4)):             
            if int(SI) < 15000:
                pls_base = int(SI) * 0.029
            elif int(SI) < 40001:
                pls_base = int(SI) * 0.026                               
            pls_min = 300 #220 
        
            if int(sport_loading(Make,Model)) == 1:
                pls_base = int(SI) * 0.057
                pls_min = 440 #360                 
        else:
            #return 5 # Recommend Comprehensive standard, Nil, or TPL only 
            pls_base = 0
            pls_min = 0                  

    std_base = std_base - 30
    nil_base = nil_base - 30
    pls_base = pls_base - 30

    if std_base < std_min:
        std_base = std_min
    if nil_base < nil_min:
        nil_base = nil_min
    if pls_base < pls_min:
        pls_base = pls_min            
    
    # returned base premium is exclusive of RSA and VAT
    return round(std_base,3), round(nil_base,3), round(pls_base,0)

def new_client(cpr,ename,aname,dob,nationality,city,tel,mobile,address):
    con = cx_Oracle.connect('LIBCDE/xxxxxxxxx@xx.xx.xx.xx/amandb')
    cur = con.cursor()

    p_cust_no                   =   cur.var(int)
    p_branch                    =   1
    p_office                    =   1
    p_cpr_cr                    =   cpr
    p_ename                     =   ename
    p_aname                     =   aname
    p_cust_type                 =   2
    p_broker                    =   None
    p_dob                       =   dob
    p_nationality               =   int(nationality)
    p_profession                =   1
    p_cust_city                 =   city 
    p_cust_zip_code             =   None
    p_cust_bo_box               =   None
    p_cust_home_tel1            =   tel
    p_cust_work_tel1            =   None
    p_cust_mobile               =   mobile 
    p_full_address              =   address
    p_file_no                   =   None
 
    result = cur.callproc('LIBCDE.INSERT_CUST',
        [p_cust_no,
         p_branch,
         p_office,
         p_cpr_cr,
         p_ename,
         p_aname,
         p_cust_type,
         p_broker,
         p_dob,
         p_nationality,
         p_profession,
         p_cust_city,
         p_cust_zip_code,
         p_cust_bo_box,
         p_cust_home_tel1,
         p_cust_work_tel1,
         p_cust_mobile,
         p_full_address,
         p_file_no])  

    cur.close()
    con.close()

    return result[0]

def new_pol(policy_type,
            eff_date,
            exp_date,
            cust_no,
            client_ename,
            client_aname,
            insured_ename,
            rsa_provider,
            vehicle_make,
            vehicle_model,
            type_of_body,
            plate_type,
            class_of_use,
            registration_no,
            year_of_make,
            seating_capacity,
            SI,
            rate,
            basic_prem,
            total_prem,
            rsa_prem,
            chassis_no,
            remarks,
            deductable,
            engine_capacity,
            driver_name,
            net_prem,
            tariff,
            vat_pcnt,
            vat_amt,
            final_tot_amt): 
    con = cx_Oracle.connect('LIBCDE/xxxxxxxxx@xx.xx.xx.xx/amandb')
    cur = con.cursor()
    cur.execute("""ALTER SESSION SET NLS_DATE_FORMAT = 'DD/MM/YYYY'""")
    
    P_BRANCH                     = 1
    P_OFFICE                     = 1
    P_CLASS_OF_BUSINESS          = 1
    P_POLICY_TYPE                = int(policy_type)                         # 1 for Comp & 2 for TPL
    P_ISSUE_DATE                 = (datetime.now()).strftime("%d/%m/%Y")        
    P_PAYMENT_MODE               = 1
    P_HIJRI_EFF_DATE             = None             
    P_HIJRI_EXP_DATE             = None
    P_EFF_DATE                   = eff_date 
    P_EXP_DATE                   = exp_date 
    P_COPY_POL_NO                = None
    P_COPY_POL_YEAR              = None
    P_CLIENT_CODE                = int(cust_no)
    P_CLIENT_ENAME               = client_ename
    P_CLIENT_ANAME               = client_aname
    P_CUST_NO                    = int(cust_no)
    P_INSURED_ENAME              = insured_ename
    P_INSURED_ANAME              = None                 
    P_BROKER                     = None                                
    P_BROKER_COMM_PCNT           = None                                    
    P_BROKER_COMM_AMT            = None     
    try:
        P_RSA_PROVIDER           = int(rsa_provider)
    except:
        P_RSA_PROVIDER           = None      
    P_BENEFICIARY_NO             = None
    P_ID_NO                      = None
    P_OCCUPATION                 = None
    P_NATIONALITY                = None
    P_CITY                       = None
    P_HOME_TEL                   = None
    P_OFFICE_TEL                 = None
    P_MOBILE                     = None
    P_DOB                        = None
    P_AGE                        = None
    P_VEHICLE_MAKE               = int(vehicle_make)
    P_VEHICLE_MODEL              = int(vehicle_model)
    P_TYPE_OF_BODY               = int(type_of_body)
    P_PLATE_TYPE                 = int(plate_type)                  
    P_EVCL_CUSTOM_ID             = None
    P_CLASS_OF_USE               = int(class_of_use)                # 1 for Private & 2 for Commercial
    P_PLATE_NO                   = registration_no
    P_ENGINE_NO                  = None
    P_NO_OF_CYLINDERS            = None
    P_YEAR_OF_MAKE               = int(year_of_make)
    P_SEATING_CAPACITY           = int(seating_capacity)
    try:
        P_SI                     = int(SI)
    except:
        P_SI                     = None    
    P_RATE                       = float(rate)
    P_BASIC_PREM                 = float(basic_prem)
    P_TOTAL_PREM                 = float(total_prem)
    P_ADD_PREM                   = 0
    P_ROAD_ASSIST                = float(rsa_prem)
    P_DISCOUNT                   = 0
    P_DEPRECIATION               = None
    P_CHASSIS_NO                 = chassis_no
    P_REMARKS                    = remarks
    P_ADDRESS                    = None
    P_BUS_LOCATION               = 1
    P_VEHICLE_COLOR              = None
    P_DEDUCTABLE                 = float(deductable)                    # SI < 10,000 is 50 and > 10,000 is 100; 0 for TPL
    P_ENGINE_CAPACITY            = int(engine_capacity)
    P_PER_ACC_DRV                = 0
    P_PAD_COVER_PCNT             = None
    P_PAD_COVER_AMT              = None
    P_PER_ACC_DRV_PASS           = None
    P_PADP_COVER_PCNT            = None
    P_PADP_COVER_AMT             = None
    P_AGENCY_REPAIR              = 2                
    P_ER_COVER_PCNT              = None
    P_ER_COVER_AMT               = None
    P_CON_NAT                    = None
    P_CN_COVER_PCNT              = None
    P_CN_COVER_AMT               = None
    P_BETWEEB_AGE                = None
    P_BA_COVER_PCNT              = None
    P_BA_COVER_AMT               = None
    P_LESSTHAN_AGE               = None
    P_LA_COVER_PCNT              = None
    P_LA_COVER_AMT               = None
    P_ADJUST_FLAG                = None
    P_CUST_ZIP_CODE              = None
    P_CUST_PO_BOX                = None
    P_DRIVER_NAME                = driver_name
    P_AGENCY_FLAG                = 2
    P_USER_ID                    = 'WebAdmin'
    P_POL_NO                     = cur.var(int)
    P_POL_YEAR                   = cur.var(int)
    P_DRIVER_BIRTH_DT            = None
    P_DRIVER_IQAMA_NO            = None
    P_DRIVER_LICENSE_TYPE        = None
    P_REF_NO                     = None
    P_BROKER_NO                  = None
    P_SOURCE                     = 1            # Direct Business
    P_REC_ID                     = cur.var(int)
    P_AGENT_NAME                 = None
    P_AGENT_COMM_AMT             = None
    P_NET_PREM                   = float(net_prem)
    P_SERVICE_CHARGE             = 0
    P_ADD_TAX                    = 0
    P_ISSUE_FEE                  = 0
    P_STAMP_FEE                  = 0
    P_ICF_FEE                    = 0
    P_GATR_PREM                  = float(rsa_prem)
    P_POST_FLAG                  = cur.var(int)
    P_REI_FLAG                   = cur.var(int)
    P_CLIENT_VOH_NO              = cur.var(int)
    P_CLIENT_VOH_TYPE            = cur.var(int)
    P_CLIENT_VOH_YEAR            = cur.var(int)
    P_AGENT_VOH_NO               = cur.var(int)
    P_AGENT_VOH_TYPE             = cur.var(int)
    P_AGENT_VOH_YEAR             = cur.var(int)
    P_SEQUENCE_NO                = 0
    P_CUST_CLASS                 = None
    P_EGOV_FLAG                  = None                                                     
    P_TARIFF_PKG                 = int(tariff)          # 1 for Comp, 2 for TPL, 7 for Plus, & 22 for Nil
    P_VAT_PCNT                   = int(vat_pcnt)
    P_VAT_AMT                    = float(vat_amt)
    P_FINAL_TOT_AMT              = float(final_tot_amt)
    P_VAT_COMM_PCNT              = 0                                                       
    P_VAT_COMM_AMT               = 0                                                        
    P_FILE_NO                    = None
    print("Pre-issuance")
    result = cur.callproc('LIBCDE.insert_new_policy',
        [P_BRANCH,
         P_OFFICE,
         P_CLASS_OF_BUSINESS,
         P_POLICY_TYPE,
         P_ISSUE_DATE,
         P_PAYMENT_MODE,
         P_HIJRI_EFF_DATE,
         P_HIJRI_EXP_DATE,
         P_EFF_DATE,
         P_EXP_DATE,
         P_COPY_POL_NO,
         P_COPY_POL_YEAR,
         P_CLIENT_CODE,
         P_CLIENT_ENAME,
         P_CLIENT_ANAME,
         P_CUST_NO,
         P_INSURED_ENAME,
         P_INSURED_ANAME,
         P_BROKER,
         P_BROKER_COMM_PCNT,
         P_BROKER_COMM_AMT,
         P_RSA_PROVIDER,
         P_BENEFICIARY_NO,
         P_ID_NO,
         P_OCCUPATION,
         P_NATIONALITY,
         P_CITY,
         P_HOME_TEL,
         P_OFFICE_TEL,
         P_MOBILE,
         P_DOB,
         P_AGE,
         P_VEHICLE_MAKE,
         P_VEHICLE_MODEL,
         P_TYPE_OF_BODY,
         P_PLATE_TYPE,
         P_EVCL_CUSTOM_ID,
         P_CLASS_OF_USE,
         P_PLATE_NO,
         P_ENGINE_NO,
         P_NO_OF_CYLINDERS,
         P_YEAR_OF_MAKE,
         P_SEATING_CAPACITY,
         P_SI,
         P_RATE,
         P_BASIC_PREM,
         P_TOTAL_PREM,
         P_ADD_PREM,
         P_ROAD_ASSIST,
         P_DISCOUNT,
         P_DEPRECIATION,
         P_CHASSIS_NO,
         P_REMARKS,
         P_ADDRESS,
         P_BUS_LOCATION,
         P_VEHICLE_COLOR,
         P_DEDUCTABLE,
         P_ENGINE_CAPACITY,
         P_PER_ACC_DRV,
         P_PAD_COVER_PCNT,
         P_PAD_COVER_AMT,
         P_PER_ACC_DRV_PASS,
         P_PADP_COVER_PCNT,
         P_PADP_COVER_AMT,
         P_AGENCY_REPAIR,
         P_ER_COVER_PCNT,
         P_ER_COVER_AMT,
         P_CON_NAT,
         P_CN_COVER_PCNT,
         P_CN_COVER_AMT,
         P_BETWEEB_AGE,
         P_BA_COVER_PCNT,
         P_BA_COVER_AMT,
         P_LESSTHAN_AGE,
         P_LA_COVER_PCNT,
         P_LA_COVER_AMT,
         P_ADJUST_FLAG,
         P_CUST_ZIP_CODE,
         P_CUST_PO_BOX,
         P_DRIVER_NAME,
         P_AGENCY_FLAG,
         P_USER_ID,
         P_POL_NO,
         P_POL_YEAR,
         P_DRIVER_BIRTH_DT,
         P_DRIVER_IQAMA_NO,
         P_DRIVER_LICENSE_TYPE,
         P_REF_NO,
         P_BROKER_NO,
         P_SOURCE,
         P_REC_ID,
         P_AGENT_NAME,
         P_AGENT_COMM_AMT,
         P_NET_PREM,
         P_SERVICE_CHARGE,
         P_ADD_TAX,
         P_ISSUE_FEE,
         P_STAMP_FEE,
         P_ICF_FEE,
         P_GATR_PREM,
         P_POST_FLAG,
         P_REI_FLAG,
         P_CLIENT_VOH_NO,
         P_CLIENT_VOH_TYPE,
         P_CLIENT_VOH_YEAR,
         P_AGENT_VOH_NO,
         P_AGENT_VOH_TYPE,
         P_AGENT_VOH_YEAR,
         P_SEQUENCE_NO,
         P_CUST_CLASS,
         P_EGOV_FLAG,
         P_TARIFF_PKG,
         P_VAT_PCNT,
         P_VAT_AMT,
         P_FINAL_TOT_AMT,
         P_VAT_COMM_PCNT,
         P_VAT_COMM_AMT,
         P_FILE_NO])        
    print("result: ",tuple(result))
    print("Finished processing insert. Now going to collect Schedule data.")    
    cur.close()
    con.close()
    return result[82],result[83]

def get_schedule_data(pol_no,pol_year): 
    (endt_no,endt_year) = get_latest_endt(int(pol_no),int(pol_year))
    print(endt_no,endt_year)
    
    con = cx_Oracle.connect('LIBCDE/xxxxxxxxx@xx.xx.xx.xx/amandb')
    cur1 = con.cursor()

    p_lang                      =   1
    p_branch                    =   1              
    p_office                    =   1   
    p_ecar_class_of_business    =   1
    p_ecar_endt_no              =   endt_no            
    p_ecar_year                 =   endt_year           
    p_ecar_endt_type            =   0           
    p_pol_no                    =   int(pol_no)
    p_pol_year                  =   int(pol_year)
    p_broker_value              =   None
    p_policy_no                 =   cur1.var(str)
    p_policy_type               =   cur1.var(str)
    p_eff                       =   cur1.var(str)
    p_exp                       =   cur1.var(str)
    p_issue                     =   cur1.var(str)
    p_insured                   =   cur1.var(str)
    p_address                   =   cur1.var(str)
    p_vehicle_make              =   cur1.var(str)
    p_vehicle_model             =   cur1.var(str)
    p_registration_no           =   cur1.var(str)
    p_chassis_no                =   cur1.var(str)
    p_year_of_make              =   cur1.var(int)
    p_class_of_use              =   cur1.var(str)
    p_seat_capacity             =   cur1.var(int)
    p_value                     =   cur1.var(str)
    p_deductible                =   cur1.var(str)
    p_vol_excess                =   cur1.var(str)
    p_bus_loc                   =   cur1.var(str)
    p_ecar_bus_location         =   cur1.var(int)
    p_cover_desc                =   cur1.var(str)
    p_excluding_desc            =   cur1.var(str)
    p_evcl_accessories          =   cur1.var(str)
 
    result1 = cur1.callproc('WEB_INSERT_DIRECT_AMAN.get_schedule_data',
        [p_lang,
         p_branch,
         p_office,
         p_ecar_class_of_business,
         p_ecar_endt_no,
         p_ecar_year,
         p_ecar_endt_type,
         p_pol_no,
         p_pol_year,
         p_broker_value,
         p_policy_no,
         p_policy_type,
         p_eff,
         p_exp,
         p_issue,
         p_insured,
         p_address,
         p_vehicle_make,
         p_vehicle_model,
         p_registration_no,
         p_chassis_no,
         p_year_of_make,
         p_class_of_use,
         p_seat_capacity,
         p_value,
         p_deductible,
         p_vol_excess,
         p_bus_loc,
         p_ecar_bus_location,
         p_cover_desc,
         p_excluding_desc,
         p_evcl_accessories])  

    cur1.close()
    
    print(tuple(result1))

    cur2 = con.cursor()
    cur2.execute("""select VUW_CLIENT_VOH_NO,       
                           VUW_ACC_CLIENT_VOH_YEAR, 
                           CLASS_OF_USE_DESC usage, 
                           DEDUCTABLE,              
                           RSA_PROVIDER,           
                           (select CRR_ENAME 
                               from CARCDE.CAR_RSA_RATING
                               where CRR_CODE=RSA_PROVIDER
                               and CRR_POL_TYPE=VUW_POL_TYPE) RSA,         
                           (select nvl(CUST_ACCOUNT_NO,'10027601000000') 
                               from gencde.customers
                               where cust_no=VUW_CLIENT_NO) account_no,     
                           (select CUST_VAT_FILE 
                               from gencde.customers
                               where cust_no=VUW_CLIENT_NO) customer_vat,  
                           (select LIBCDE.get_sys_desc_web (101,nvl(EVCL_VEHICLE_MAKE,OVCL_VEHICLE_MAKE),2) 
                               from carcde.car_vehicle_endt
                               where EVCL_ENDT_NO = VUW_ENDT_NO
                               and EVCL_YEAR=VUW_ENDT_YEAR
                               and EVCL_VEHICLE_SERIAL=1
                               and EVCL_ENDT_TYPE=0) Make,                  
                           (select LIBCDE.get_sys_desc_web (110,nvl(EVCL_VEHICLE_MODEL,OVCL_VEHICLE_MODEL),2) 
                               from carcde.car_vehicle_endt
                               where EVCL_ENDT_NO = VUW_ENDT_NO
                               and EVCL_YEAR=VUW_ENDT_YEAR
                               and EVCL_VEHICLE_SERIAL=1
                               and EVCL_ENDT_TYPE=0) Model,                
                           (select nvl(vvcl_accessories,'Nil')  
                               from carcde.vcar_vehicle_endt  
                               where vvcl_branch = 1
                               and vvcl_office = 1
                               and vvcl_endt_no = VUW_ENDT_NO
                               and vvcl_year = VUW_ENDT_YEAR
                               and vvcl_endt_type = 0
                               and VVCL_VEHICLE_SERIAL=1) Accessories,      
                           decode ((select sys_lsdesc 
                                      from gencde.systemf
                                     where sys_major = 106
                                       and sys_minor= (SELECT  VCOV_CODE 
                                                         FROM CARCDE.vCAR_COVER_ENDT
                                                        WHERE  vCOV_branch = 1
                                                          AND vCOV_office = 1
                                                          AND vCOV_endt_no = VUW_ENDT_NO
                                                          AND vCOV_year = VUW_ENDT_YEAR
                                                          AND vCOV_endt_type = 0)) || ' ' ||
                                    (select CRR_ENAME 
                                       from CARCDE.CAR_RSA_RATING
                                      where CRR_CODE=RSA_PROVIDER
                                        and CRR_POL_TYPE=VUW_POL_TYPE),' ','Nil',
                                    (select sys_lsdesc 
                                       from gencde.systemf
                                      where sys_major = 106
                                        and sys_minor= (SELECT VCOV_CODE 
                                                          FROM CARCDE.vCAR_COVER_ENDT
                                                         WHERE vCOV_branch = 1
                                                           AND vCOV_office = 1
                                                           AND vCOV_endt_no = VUW_ENDT_NO
                                                           AND vCOV_year = VUW_ENDT_YEAR
                                                           AND vCOV_endt_type = 0)) || ' ' ||
                                    (select CRR_ENAME 
                                       from CARCDE.CAR_RSA_RATING
                                      where CRR_CODE=RSA_PROVIDER
                                        and CRR_POL_TYPE=VUW_POL_TYPE)) additional_cover,
                           decode ((SELECT LIBCDE.get_sys_desc_web (106,VCOV_CODE,2) 
                                      FROM CARCDE.vCAR_COVER_ENDT
                                     WHERE vCOV_branch = 1
                                       AND vCOV_office = 1
                                       AND vCOV_endt_no = VUW_ENDT_NO
                                       AND vCOV_year = VUW_ENDT_YEAR
                                       AND vCOV_endt_type = 0) || ' ' ||
                                   (select CRR_ENAME 
                                      from CARCDE.CAR_RSA_RATING
                                     where CRR_CODE=RSA_PROVIDER
                                       and CRR_POL_TYPE=VUW_POL_TYPE),' ','Nil',
                                   (SELECT LIBCDE.get_sys_desc_web (106,VCOV_CODE,2) 
                                      FROM CARCDE.vCAR_COVER_ENDT
                                     WHERE vCOV_branch = 1
                                       AND vCOV_office = 1
                                       AND vCOV_endt_no = VUW_ENDT_NO
                                       AND vCOV_year = VUW_ENDT_YEAR
                                       AND vCOV_endt_type = 0) || ' ' ||
                                   (select CRR_ENAME 
                                      from CARCDE.CAR_RSA_RATING
                                     where CRR_CODE=RSA_PROVIDER
                                       and CRR_POL_TYPE=VUW_POL_TYPE)) additional_conditions,
                           VUW_CLIENT_NO,                                                                                                                 
                           BODY_TYPE_DESC,                                      
                           '200000513800002' company_vat,
                           VUW_TOTAL_PREM,                                                                                                                    
                           VUW_VAT_PCNT,
                           VUW_VAT_AMT,
                           VUW_TOTAL_PREM + VUW_VAT_AMT Final_Total,
                           (SELECT CUST_ANAME 
                              from gencde.customers 
                             where CUST_NO = VUW_AGENT_NO) broker,
                           (SELECT ca_full_address 
                              FROM gencde.cust_address
                             WHERE ca_cust_no = VUW_CLIENT_NO) address                             
                       from PLNCDE.VPLN_UW_VIEW_MACAW
                       where VUW_ENDT_NO  = """ + "'" + str(endt_no) + "'" + """
                       and VUW_ENDT_YEAR = """ + "'" + str(endt_year) + "'" + """
                       and VUW_DEPT_NO=1
                       and VUW_ENDT_TYPE=0""")               
    result2 = cur2.fetchall()

    print(tuple(result2))
    
    pol_no =         result1[7]
    pol_year =       result1[8]
    broker =         result2[0][20]
    pol_type =       result1[11]
    eff_dt =         (((result1[12]).__str__()).split(" "))[0]
    exp_dt =         (((result1[13]).__str__()).split(" "))[0]
    issue_dt =       (((result1[14]).__str__()).split(" "))[0]
    client_name =    result1[15]
    address =        result2[0][21] 
    make =           result2[0][8] 
    model =          result2[0][9] 
    registration =   result1[19]
    chassis_no =     result1[20]
    year_of_make =   result1[21]
    usage =          result2[0][2] 
    passengers =     result1[23]
    si =             result1[24]
    deductible =     result2[0][3] 
    add_exclusions = result1[30]
    accessories =    result2[0][10] 
    voh_no =         result2[0][0]
    add_cover =      result2[0][11]
    add_conditions = result2[0][12]
    cust_no =        result2[0][13] 
    body_type =      result2[0][14]
    company_vat =      result2[0][15]
    total_prem =     result2[0][16]
    vat_pct =        result2[0][17]
    vat_amt =        result2[0][18]
    final_tot =      result2[0][19]
    rsa =            result2[0][5]
    cust_vat =       result2[0][7]  

    cur2.close()
    con.close()

    try:
        generateShedPdf('C:\inetpub\wwwroot\prints/Schedule-'+str(pol_no)+'-'+str(pol_year)+'.pdf',{"participant":           client_name,
                                                                                "policy_type":            pol_type,
                                                                                "policy_number":          "BAH/MOT/"+str(pol_year)[-2:]+"/"+str(pol_no),
                                                                                "from_date":              eff_dt,
                                                                                "to_date":                exp_dt,
                                                                                "registeration_no":       registration,
                                                                                "address":                address,
                                                                                "make_year":              year_of_make,           
                                                                                "chassis":                chassis_no,             
                                                                                "usage":                  usage,                  
                                                                                "make":                   make,                   
                                                                                "model":                  model,                  
                                                                                "excess":                 deductible,                 
                                                                                "passengers":             passengers,             
                                                                                "si":                     si,
                                                                                "compulsory_deductible":  deductible,             
                                                                                "additional_conditions":  add_conditions,         
                                                                                "additional_exclusions":  add_exclusions,         
                                                                                "accessories":            accessories,            
                                                                                "print_date":             str((datetime.now()).strftime("%d/%m/%Y")),
                                                                                "additional_cover":       add_cover,              
                                                                                "issue_date":             issue_dt})
    except:
        print('Schedule is generated!')
    
    try:    
        generateDnPdf('C:\inetpub\wwwroot\prints/Tax_Invoice-'+str(pol_no)+'-'+str(pol_year)+'.pdf',{"name":                client_name,
                                                                                "date":                  issue_dt,
                                                                                "company_vat":             company_vat,            
                                                                                "address":               address,
                                                                                "voucher_no":            voh_no,                 
                                                                                "broker":                broker,
                                                                                "account_no":            "10027601000000",       
                                                                                "customer_id":           cust_no,
                                                                                "customer_vat":          cust_vat,      
                                                                                "policy_number":         "BAH/MOT/"+str(pol_year)[-2:]+"/"+str(pol_no),
                                                                                "endorsement_year":      "BAH/MOT/"+str(endt_year)[-2:]+"/"+str(endt_no),
                                                                                "policy_type":           pol_type,
                                                                                "from_date":             eff_dt,
                                                                                "to_date":               exp_dt,
                                                                                "registeration_no":      registration,
                                                                                "vehicle_type":          body_type,
                                                                                "chassis":               chassis_no,
                                                                                "rsa":                   rsa,    
                                                                                "total_before_vat":      total_prem,
                                                                                "vat_percentage":        vat_pct,
                                                                                "total_after_vat":       vat_amt,
                                                                                "total_due":             final_tot,
                                                                                "amount_in_words":       "", 
                                                                                "printed_by":            "webadmin"})
    except:
        print('Invoice is generated!')
    
    return 'ok'

def get_latest_endt(pol_no,pol_year):
    con = cx_Oracle.connect('LIBCDE/xxxxxxxxx@xx.xx.xx.xx/amandb')
    cur = con.cursor()
    cur.execute("""SELECT DISTINCT ECAR_ENDT_NO,
                          ECAR_YEAR,
                          ECAR_ENDT_TYPE,
                          ECAR_TRN_TYPE,
                          ECAR_POL_NO,
                          ECAR_POL_YEAR,
                          libcde.get_sys_desc_web (29, ECAR_POLICY_TYPE, 2), 
                          ECAR_SOURCE,
                          ECAR_ENDT_DT,
                          ECAR_INS_ST_DT,
                          ECAR_INS_ED_DT,
                          ECAR_UW_YEAR,
                          ECAR_CLIENT,
                          ECAR_CLIENT_NAME,
                          ECAR_CUST_NO,
                          ECAR_CUST_NAME,
                          ECAR_NET_PREM,
                          ECAR_DISCOUNTS,
                          ECAR_LOADINGS,
                          ECAR_GATR_PREM RSA,
                          ECAR_ISSUE_FEE,
                          ECAR_TOTAL_PREM,
                          nvl(ECAR_VAT_AMT,0) VAT_Amount,
                          nvl (ECAR_FINAL_TOTAL,ECAR_TOTAL_PREM) Final_Total
                     FROM carcde.car_ins_endt
                    WHERE ECAR_POL_NO= """ + "'" + str(pol_no) + "'" + """
                      AND ECAR_POL_YEAR = """ + "'" + str(pol_year) + "'" + """
                      AND ECAR_POST_FLAG > 0
                      AND ECAR_YEAR = EXTRACT(YEAR FROM SYSDATE)
                     -- AND ECAR_TRN_TYPE = 3
                    ORDER BY ECAR_ENDT_DT DESC """)               
    result = cur.fetchall()
    cur.close()
    con.close() 
    print(result[0][0]) 
    return result[0][0],result[0][1]   

def getip(ipAddress):
    url = "https://freegeoip.app/json/"+ipAddress
    headers = {
        'accept': "application/json",
        'content-type': "application/json"
        }
    response = requests.request("GET", url, headers=headers)
    result = json.loads(response.text)

    if str(result["country_code"]) == 'BH':
        return "Ok"
    else:
        return "Forbidden"

class lapsed(Resource):
    def post(self):
        params = [0,0,0,0,0]
        parameters = request.get_json()
        json_data = json.loads(json.dumps(parameters))
        params[0] = json_data["egov"]["cpr"]
        params[1] = json_data["egov"]["type"]   
        params[2] = json_data["egov"]["reg_no"]
        params[3] = json_data["egov"]["reg_type"]
        params[4] = json_data["egov"]["chassis"] 
        query_resp = egov(params[0],params[1],params[2],params[3],params[4])                
        try:
            return jsonify({"egov":{                 
                                "result": query_resp[0],
                                "expiry":query_resp[1]}})    
        except:
            return jsonify({"failure": query_resp})

class rsa_cost(Resource):
    def post(self):
        params = [0]
        parameters = request.get_json()
        json_data = json.loads(json.dumps(parameters))
        params[0] = json_data["rsa"]["rsa_option"]   
        query_resp = rsa_loading(params[0])                
        try:
            return jsonify({"rsa":{                
                                "rsa_loading": query_resp}})    
        except:
            return jsonify({"failure": query_resp})
             
class age_cost(Resource):
    def post(self):
        params = [0,0,0]
        parameters = request.get_json()
        json_data = json.loads(json.dumps(parameters))
        params[0] = json_data["age"]["driver_age"]
        params[1] = json_data["age"]["tariff"]   
        params[2] = json_data["age"]["base_prem"]    
        query_resp = age_loading(params[0],params[1],params[2])                
        try:
            return jsonify({"age":{
                                "age_loading": query_resp}})    
        except:
            return jsonify({"failure": query_resp})

class tpl_quote(Resource):
    def post(self):
        params = [0,0,0,0,0,0]
        parameters = request.get_json()
        json_data = json.loads(json.dumps(parameters))
        params[0] = json_data["tpl"]["make"]
        params[1] = json_data["tpl"]["model"]   
        params[2] = json_data["tpl"]["reg_type"]
        params[3] = json_data["tpl"]["engine_cc"]
        params[4] = json_data["tpl"]["seats"]
        params[5] = json_data["tpl"]["ncc"]   
        query_resp = new_quote_tpl(params[0],params[1],params[2],params[3],params[4],params[5])                
        try:
            return jsonify({"tpl":{                 
                                "tpl_prem": query_resp}})    
        except:
            return jsonify({"failure": query_resp})

class comp_quote(Resource):
    def post(self):
        params = [0,0,0,0,0,0,0,0,0]
        parameters = request.get_json()
        json_data = json.loads(json.dumps(parameters))
        params[0] = json_data["comprehensive"]["make"]
        params[1] = json_data["comprehensive"]["model"]    
        params[2] = json_data["comprehensive"]["reg_type"]
        params[3] = json_data["comprehensive"]["year_of_make"]  
        params[4] = json_data["comprehensive"]["new"]  
        params[5] = json_data["comprehensive"]["seats"]  
        params[6] = json_data["comprehensive"]["si"]
        params[7] = json_data["comprehensive"]["ncc"]                            
        query_resp = new_quote_comp(params[0],params[1],params[2],params[3],params[4],params[5],params[6],params[7])                
        try:
            return jsonify({"comprehensive":{
                                "std_prem": query_resp[0],
                                "nil_prem": query_resp[1],                  
                                "pls_prem": query_resp[2]}})    
        except:
            return jsonify({"failure": query_resp})

class setup_client(Resource):
    @token_required
    def post(self):
        params = [0,0,0,0,0,0,0,0,0]
        parameters = request.get_json()
        json_data = json.loads(json.dumps(parameters))
        params[0] = json_data["client"]["cpr"]   
        params[1] = json_data["client"]["ename"]   
        params[2] = json_data["client"]["aname"]   
        params[3] = json_data["client"]["dob"]   
        params[4] = json_data["client"]["nationality"]   
        params[5] = json_data["client"]["city"]   
        params[6] = json_data["client"]["tel"]   
        params[7] = json_data["client"]["mobile"]   
        params[8] = json_data["client"]["address"]   
        query_resp = new_client(params[0],params[1],params[2],params[3],params[4],params[5],params[6],params[7],params[8])                
        try:
            return jsonify({"client":{                
                                "response": query_resp}})    
        except:
            return jsonify({"failure": query_resp})
 
class issue_pol(Resource):
    @token_required
    def post(self):
        params = [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]
        parameters = request.get_json()
        json_data = json.loads(json.dumps(parameters))
        params[0] = json_data["issue"]["policy_type"]   
        params[1] = json_data["issue"]["eff_date"]
        params[2] = json_data["issue"]["exp_date"]
        params[3] = json_data["issue"]["cust_no"]
        params[4] = json_data["issue"]["client_ename"]
        params[5] = json_data["issue"]["client_aname"]
        params[6] = json_data["issue"]["insured_ename"]
        params[7] = json_data["issue"]["rsa_provider"]
        params[8] = json_data["issue"]["vehicle_make"]
        params[9] = json_data["issue"]["vehicle_model"]
        params[10] = json_data["issue"]["type_of_body"]
        params[11] = json_data["issue"]["plate_type"]
        params[12] = json_data["issue"]["class_of_use"]
        params[13] = json_data["issue"]["registration_no"]
        params[14] = json_data["issue"]["year_of_make"]
        params[15] = json_data["issue"]["seating_capacity"]
        params[16] = json_data["issue"]["SI"]
        params[17] = json_data["issue"]["rate"]
        params[18] = json_data["issue"]["basic_prem"]
        params[19] = json_data["issue"]["total_prem"]
        params[20] = json_data["issue"]["rsa_prem"]
        params[21] = json_data["issue"]["chassis_no"]
        params[22] = json_data["issue"]["remarks"]
        params[23] = json_data["issue"]["deductable"]
        params[24] = json_data["issue"]["engine_capacity"]
        params[25] = json_data["issue"]["driver_name"]
        params[26] = json_data["issue"]["net_prem"]
        params[27] = json_data["issue"]["tariff"]
        params[28] = json_data["issue"]["vat_pcnt"]
        params[29] = json_data["issue"]["vat_amt"]
        params[30] = json_data["issue"]["final_tot_amt"]
        query_resp = new_pol(params[0],params[1],params[2],params[3],params[4],params[5],params[6],params[7],params[8],params[9],
                             params[10],params[11],params[12],params[13],params[14],params[15],params[16],params[17],params[18],params[19],
                             params[20],params[21],params[22],params[23],params[24],params[25],params[26],params[27],params[28],params[29],
                             params[30])                
        try:
            return jsonify({"issue":{                
                                "pol_no": query_resp[0],
                                "pol_year": query_resp[1]}})    
        except:
            return jsonify({"failure": query_resp})

class print_docs(Resource):
    @token_required
    def post(self):
        params = [0,0]
        parameters = request.get_json()
        json_data = json.loads(json.dumps(parameters))
        params[0] = json_data["print"]["pol_no"]   
        params[1] = json_data["print"]["pol_year"]   
        query_resp = get_schedule_data(params[0],params[1])                
        try:
            return jsonify({"print":{                
                                "result": query_resp}})    
        except:
            return jsonify({"failure": query_resp})

class geoip(Resource):
    def post(self):
        params = [0]
        parameters = request.get_json()
        json_data = json.loads(json.dumps(parameters))
        params[0] = json_data["geoip"]["ipAddress"]  
        query_resp = getip(params[0])                
        try:
            return jsonify({"geoip":{                
                                "result": query_resp}})    
        except:
            return jsonify({"failure": query_resp})

if __name__ == '__name__':
    app.run(debug=True)

api.add_resource(lapsed, '/egov')    
api.add_resource(rsa_cost, '/rsa')
api.add_resource(age_cost, '/age')
api.add_resource(tpl_quote, '/tpl')
api.add_resource(comp_quote, '/comprehensive')
api.add_resource(setup_client, '/client')
api.add_resource(issue_pol, '/issue')
api.add_resource(print_docs, '/print')
api.add_resource(geoip, '/geoip')

 