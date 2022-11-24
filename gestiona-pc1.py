#!/usr/bin/python3
import sys  # Leer y modificar ficheros
import subprocess
from subprocess import STDOUT, check_call
import os
import logging
from lxml import etree

#Lista de nombre para los servidores
servers_name=["c1","lb","s1","s2","s3","s4","s5"]
vms=list()

#Verifica cuantos servidores hay que crear
def readJSON_server():
    jsonfound = subprocess.run(
        ["ls", "gestiona-pc1.json"], stdout=open(os.devnull, 'wb'), stderr=STDOUT) # 0: si existe y 1: si no existe
    if not jsonfound.returncode:
        #os.system("cat gestiona-pc1.json | grep num_serv | awk '{print$NF}'")
        fin = open('gestiona-pc1.json', 'r')  # in file
        for line in fin:
            if "num_serv" in line:
                if "1" in line:
                    return 1
                elif "2" in line:
                    return 2
                elif "3" in line:
                    return 3
                elif "4" in line:
                    return 4
                elif "5" in line:
                    return 5
                else:
                    logger.debug("Por defecto, asignamos dos servidores")
                    return 2
        fin.close()
    else:
        return 0

#Verifica si el debugmode está activado y devuelve un bool dependiendo de si está activado o no
debugmode = False
def readJSON_debugmode():
    jsonfound = subprocess.run(
        ["ls", "gestiona-pc1.json"], stdout=open(os.devnull, 'wb'), stderr=STDOUT)
    if not jsonfound.returncode:
        #os.system("cat gestiona-pc1.json | grep debug | awk '{print$NF}'")
        fin = open('gestiona-pc1.json', 'r')  # in file
        for line in fin:
            if 'debug' in line:
                if 'true' in line:
                    return True
        fin.close()

#Datos extraidos del JSON
debugmode = readJSON_debugmode()
num_servers = readJSON_server()

def create():
    logger.debug('Creando...')
    logger.debug('Se verifica el parametro de numero de servidores')
    if len(sys.argv) == 3:
        param2 = str(sys.argv[2])
    else:
        logger.debug('El número de servidores web a arrancar está fuera de los límites permitidos')
        logger.debug('Por ello se arrancaran el número por defecto: 2\n')
        param2 = str(2)  # Valor por defecto del número de servidores a arrancar
    json = open("gestiona-pc1.json", "w+")
    json.write('{\n\t"num_serv": '+param2+'\n}')
    json.close()

    num_servers=param2
    if num_servers is not None:
        cont = 0
        for i in servers_name:
            if str(cont) <= num_servers:
                vms.append(i)
                cont=cont+1
            else:
                vms.append(i)
                break
    logger.debug('Se aplican las configuraciones en el host')
    os.system('sudo brctl addbr LAN1')
    os.system('sudo brctl addbr LAN2')
    os.system('sudo ifconfig LAN1 up')
    os.system('sudo ifconfig LAN2 up')
    os.system("sudo ifconfig LAN1 10.20.1.3/24")
    os.system("sudo ip route add 10.20.0.0/16 via 10.20.1.1")
    os.system("chmod +rwx cdps-vm-base-pc1.qcow2")
    os.system("touch interfaces")

    for i in vms: 
        os.system("qemu-img create -f qcow2 -b cdps-vm-base-pc1.qcow2 "+i+".qcow2")
        os.system("cp plantilla-vm-pc1.xml "+i+".xml")
        logger.debug('Modificamos el fichero xml de '+i)
        tree = etree.parse(i+".xml")
        root = tree.getroot()
        domain=root.find("domain")
        name = root.find("name")
        name.text = i
        source = root.find("./devices/disk/source")
        ruta = os.path.abspath(i+".qcow2")
        source.set("file", ruta)
        if i == "c1":
            interface = root.find("./devices/interface/source")
            interface.set("bridge", "LAN1")
        if i== "lb":
            interface = root.find("./devices/interface/source")
            interface.set("bridge", "LAN1")
            interface = root.find("./devices/interface/source")
            interface.set("bridge", "LAN2")
        if i == "lb":
            interface_tag = etree.Element("interface", type="bridge")
            devices_tag = root.find("devices")
            interface_tag.text = ""
            devices_tag.append(interface_tag)
            source_tag = etree.Element("source", bridge="LAN2")
            model_tag = etree.Element("model", type="virtio")
            interface_tag.append(source_tag)
            interface_tag.append(model_tag)
        tree.write(i+".xml")

        logger.debug('Se define las MV '+i+' con el xml')
        os.system("sudo virsh define "+i+".xml")
        logger.debug('Configurando del fichero hostname de '+i)
        os.system("touch hostname")
        fin = open ("hostname","w+")
        fin.write(i)
        fin.close()
        os.system("chmod +rwx hostname")
        os.system("sudo virt-copy-in -a "+i+".qcow2 hostname /etc")
        logger.debug('Configuración de los ficheros index.html para '+i)
        if i == "s1" or i == "s2" or i == "s3" or i == "s4" or i == "s5":
            logger.debug('Copiando el archivo hostname ya que el contenido de ambos es el mismo')
            os.system("echo "+i+">index.html")
            os.system("sudo virt-copy-in -a "+i+".qcow2 index.html /var/www/html/") #error: target ‘/var/www/html’ is not a directory 
        logger.debug('Configura el archivo hosts de '+i)
        os.system("cp /etc/hosts hosts")
        fin = open ("hosts","w")
        fout = open ("/etc/hosts", "r")
        for line in fout:
            if "127.0.0.1" in line:
                fin.write("127.0.1.1\t"+i+"\n")
            else:
                fin.write(line)
        fin.close()
        fout.close()
        os.system("sudo virt-copy-in -a "+i+".qcow2 hosts /etc")
        logger.debug('Configurando el archivo interfaces de '+i)
        fout = open("interfaces","w+")
        if i == "lb":
            fout.write("auto lo \n")
            fout.write("iface lo inet loopback\n")
            fout.write("auto eth0 eth1\n")
            fout.write("iface eth0 inet static\n")
            fout.write("\taddress 10.20.1.1\n")
            fout.write("\tnetmask 255.255.255.0\n")
            fout.write("\tgateway 10.20.1.1 \n")
            fout.write("\tdns-nameservers 10.20.1.1\n")
            fout.write("iface eth1 inet static\n")
            fout.write("\taddress 10.20.2.1 \n")
            fout.write("\tnetmask 255.255.255.0\n")
            fout.write("\tgateway 10.20.2.1\n")
            fout.write("\tdns-nameservers 10.20.2.1\n")
        elif i == "c1":
            fout.write("auto lo\n")
            fout.write("iface lo inet loopback\n")
            fout.write("auto eth0\n")
            fout.write("iface eth0 inet static\n")
            fout.write("\taddress 10.20.1.2 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.1.1 \n")
            fout.write("\tdns-nameservers 10.20.1.1\n")
        elif i == "s1":
            fout.write("auto lo \n")
            fout.write("iface lo inet loopback \n")
            fout.write("auto eth0 \n")
            fout.write("iface eth0 inet static \n")
            fout.write("\taddress 10.20.2.101 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.2.1 \n")
            fout.write("\tdns-nameservers 10.20.2.1\n")
        elif i == "s2":
            fout.write("auto lo\n")
            fout.write("iface lo inet loopback\n")
            fout.write("auto eth0 \n")
            fout.write("iface eth0 inet static\n")
            fout.write("\taddress 10.20.2.102\n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.2.1 \n")
            fout.write("\tdns-nameservers 10.20.2.1\n")
        elif i == "s3":
            fout.write("auto lo\n")
            fout.write("iface lo inet loopback\n")
            fout.write("auto eth0\n")
            fout.write("iface eth0 inet static\n")
            fout.write("\taddress 10.0.2.103\n")
            fout.write("\tnetmask 255.255.255.0\n")
            fout.write("\tgateway 10.20.2.1\n")
            fout.write("\tdns-nameservers 10.20.2.1\n")
        elif i == "s4":
            fout.write("auto lo\n")
            fout.write("iface lo inet loopback\n")
            fout.write("auto eth0\n")
            fout.write("iface eth0 inet static \n")
            fout.write("\taddress 10.0.2.104\n")
            fout.write("\tnetmask 255.255.255.0\n")
            fout.write("\tgateway 10.20.2.1\n")
            fout.write("\tdns-nameservers 10.20.2.1\n")
        elif i == "s5":
            fout.write("auto eth0\n")
            fout.write("iface eth0 inet static\n")
            fout.write("\taddress 10.0.2.105\n")
            fout.write("\tnetmask 255.255.255.0\n")
            fout.write("\tgateway 10.20.2.1\n")
            fout.write("\tdns-nameservers 10.20.2.1\n")
        fout.close()
        os.system("sudo virt-copy-in -a "+i+".qcow2 interfaces /etc/network")
    logger.debug('Elimindo archivos no necesarios')
    os.system('rm interfaces')
    os.system('rm hostname')
    os.system('rm index.html')
    os.system('rm hosts')

def start():
    logger.debug('Empezando...')
    for i in vms:
        logger.debug('Iniciando maquina '+i)
        os.system('sudo virsh start '+i)

    for i in vms:
        logger.debug('Abriendo consola de la maquina '+i)
        os.system("xterm -e 'sudo virsh console "+i+"'&")

def stop():
    logger.debug('Parando...')
    # Apaga las máquinas
    for i in vms:
        logger.debug('Parando maquina '+i)
        os.system('sudo virsh shutdown '+i)

def destroy():
    logger.debug('Eliminando...')
    # Apaga forzadamente las máquinas
    for i in vms:
        logger.debug('Eliminando maquina '+i)
        os.system('sudo virsh destroy '+i)
        os.system('rm '+i+'.xml')
        os.system('rm '+i+'.qcow2')
    os.system('sudo ifconfig LAN1 down')
    os.system('sudo ifconfig LAN2 down')
    os.system('sudo brctl delbr LAN1')
    os.system('sudo brctl delbr LAN2')
    # Elimina el archivo JSON  
    os.system('rm gestiona-pc1.json')

def help():
    print('Hoja de ayuda:')
    print('gestiona-pc1.py [param1] [param2]')
    print('\n\tparam1')
    print('\t|')
    print('\t -> create: para crear los ficheros .qcow2 de diferencias y los de especificación en XML de cada MV,')
    print('\t así como los bridges virtuales que soportan las LAN del escenario. [param2] es el número de servidores')
    print('\t|')
    print('\t -> start: para arrancar las máquinas virtuales y mostrar su consola')
    print('\t|')
    print('\t -> stop: para parar las máquinas virtuales (sin liberarlas)')
    print('\t|')
    print('\t -> destroy: para liberar el escenario, borrando todos los ficheros creados')
    print('\n\tparam2 (opcional)')
    print('\t|')
    print('\t -> número de servidores web a arrancar. Configurable de 1 a 5. Por defecto se asigna 2')

# @main
if len(sys.argv) >= 2:
    param1 = str(sys.argv[1])

    if num_servers is not None:
        cont = 0
        for i in servers_name:
            if cont <= num_servers:
                vms.append(i)
                cont=cont+1
            else:
                vms.append(i)
                break
    
# Si debugmode es true, se ejecuta el debuger
    if debugmode:
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger('gestiona-pc1')
    else:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger('gestiona-pc1')

    if sys.argv[1] == 'create' and len(sys.argv) <= 3:
        create()
    elif sys.argv[1] == 'start' and len(sys.argv) == 2:
        start()
    elif sys.argv[1] == 'stop' and len(sys.argv) == 2:
        stop()
    elif sys.argv[1] == 'destroy' and len(sys.argv) == 2:
        destroy()
    else:
        help()
else:
    print("\nAlgo no ha salido bien")
    print("Algún parámetro es incorrecto o está fuera de los límites\n")
    print('Para ver la hoja de ayudas:')
    print('\t$gestiona-pc1.py help')
