#!/usr/bin/python3
import sys  # Leer y modificar ficheros
import subprocess
from subprocess import STDOUT, check_call
import os
import logging
from lxml import etree
from subprocess import call

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
                string = str(line).split()
                if string[2]=="1":
                    return 1
                elif string[2]=="2":
                    return 2
                elif string[2]=="3":
                    return 3
                elif string[2]=="4":
                    return 4
                elif string[2]=="5":
                    return 5
                else:
                    return 2
        fin.close()
    else:
        print('Debes usar el parámetro prepare, donde el nº de servidores tiene que ser de 1 a 5, tal que así:')
        print('$gestiona-pc1.py prepare [nº servidores]\n')
        return None

#Verifica si el debugmode está activado y devuelve un bool dependiendo de si está activado o no
def readJSON_debugmode():
    jsonfound = subprocess.run(
        ["ls", "gestiona-pc1.json"], stdout=open(os.devnull, 'wb'), stderr=STDOUT)
    if not jsonfound.returncode:
        #os.system("cat gestiona-pc1.json | grep num_serv | awk '{print$NF}'")
        fin = open('gestiona-pc1.json', 'r')  # in file
        for line in fin:
            if "debug" in line:
                debug = str(line).split()
                if debug[1] == 'true':
                    return True
                else:
                    return False
            else:
                return False
        fin.close()
    else:
        print('Debes usar el parámetro prepare, donde el nº de servidores tiene que ser de 1 a 5, tal que así:')
        print('$gestiona-pc1.py prepare [nº servidores]\n')
        return False

#Datos extraidos del JSON
debugmode = readJSON_debugmode()
num_servers = readJSON_server()

def prepare():
    # Verifica el parametro de numero de servidores
    if len(sys.argv) == 3:
        param2 = str(sys.argv[2])
    else:
        logger.info('El número de servidores web a arrancar está fuera de los límites permitidos')
        logger.info('Por ello se arrancaran el número por defecto: 2\n')
        param2 = str(2)  # Valor por defecto del número de servidores a arrancar
    logger.info('Preparando...')

    json = open("gestiona-pc1.json", "w+")
    json.write('{\n\t"num_serv" : '+param2+'\n}')
    json.close()

def create():
    logger.info('Creando...')
    # Cree los bridges correspondientes a las dos redes virtuales

    os.system('sudo brctl addbr LAN1')
    os.system('sudo brctl addbr LAN2')
    os.system('sudo ifconfig LAN1 up')
    os.system('sudo ifconfig LAN2 up')

    #Configuracion del host
    os.system("sudo ifconfig LAN1 10.20.1.3/24")
    os.system("sudo ip route add 10.20.0.0/16 via 10.20.1.1")

    #Da permisos a la imagen base
    call(["chmod", "777", "cdps-vm-base-pc1.qcow2"])
    #Crea las imagenes de las maquinas virtuales
    for i in servers_name: ##Cuidado con vms tamb tienes que estar sn
        call(["qemu-img", "create", "-f", "qcow2", "-b", "cdps-vm-base-pc1.qcow2", i+".qcow2"])
        call(["cp", "plantilla-vm-pc1.xml", i+".xml"])

        # Carga el fichero xml
        tree = etree.parse(i+".xml")
        # Obtiene el nodo raiz e imprimimos su nombre y el valor del atributo 'tipo'
        root = tree.getroot()
        # Buscamos la etiqueta 'nombre' y lo cambiamos
        domain = root.find("domain")
        name = root.find("name")
        name.text = i
        # Busca la etiqueta 'source' y lo cambiamos
        source = root.find("./devices/disk/source")
        #Busca la ruta absoluta de la imagen de la MV
        ruta = os.path.abspath(i+".qcow2")
        source.set("file", ruta)
        # Busca la etiqueta 'source' dentro de 'interface' y lo cambia dependiendo de la máquina
        if (i == "c1") or (i == "lb"):
            interface = root.find("./devices/interface/source")
            interface.set("bridge", "LAN1")
        else:
            interface = root.find("./devices/interface/source")
            interface.set("bridge", "LAN2")
        #Crea la interfaz para LAN 2 si es el caso de lb
        if i == "lb":
            interface_tag = etree.Element("interface", type="bridge")
            devices_tag = root.find("devices")
            interface_tag.text = ""
            devices_tag.append(interface_tag)
            source_tag = etree.Element("source", bridge="LAN2")
            model_tag = etree.Element("model", type="virtio")
            interface_tag.append(source_tag)
            interface_tag.append(model_tag)
        #Guarda el contenido del fichero XML
        tree.write(i+".xml")

        #Define las MV
        call(["sudo", "virsh", "define", str(i) + ".xml"])
        #Configuracion del fichero hostname
        call(["touch", "hostname"])
        #w+ es una orden para actualizar el contenido del fichero
        fin = open ("hostname","w+")
        fin.write(str(i))
        fin.close()
        call(["chmod", "777", "hostname"])
        #Copia a la máquina virtual el fichero
        #-a hace referencia a la imagen de la MV a la que se va a copiar
        call(["sudo", "virt-copy-in", "-a", str(i) + ".qcow2", "hostname", "/etc"])
        
        #Configuración de los ficheros index.html para los servidores
        if str(i) == "s1" or str(i) == "s2" or str(i) == "s3" or str(i) == "s4" or str(i) == "s5":
        #Copia el archivo hostname ya que el contenido de ambos es el mismo
            ###No funciona: error: target ‘/var/www/html’ is not a directory
            call(["cp", "hostname", "index.html"])
            call(["sudo", "virt-copy-in", "-a", str(i) + ".qcow2", "index.html", "/var/www/html"])
        #Configura el archivo hosts
        call(["cp", "/etc/hosts", "hosts"])
        fin = open ("hosts","w")
        fout = open ("/etc/hosts", "r")
        for line in fout:
            if "127.0.0.1 localhost" in line:
                fin.write("127.0.1.1 " + str(i) + "\n")
            else:
                fin.write(line)
        fin.close()
        fout.close()
        call(["sudo", "virt-copy-in", "-a", str(i) + ".qcow2", "hosts", "/etc"])
        #Configura el archivo interfaces
        call(["touch","interfaces"])
        fout = open("interfaces","w+")
        if str(i) == "s1":
            #Configura la ip propia
            fout.write("auto lo \n")
            fout.write("iface lo inet loopback \n\n")
            #Configura la interfaz eth0
            fout.write("auto eth0 \n")
            fout.write("iface eth0 inet static \n")
            fout.write("\taddress 10.20.2.101 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.2.1 \n")
        if str(i) == "s2":
            fout.write("auto lo \n")
            fout.write("iface lo inet loopback \n\n")
            fout.write("auto eth0 \n")
            fout.write("iface eth0 inet static \n")
            fout.write("\taddress 10.20.2.102 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.2.1 \n")
        if str(i) == "s3":
            fout.write("auto lo \n")
            fout.write("iface lo inet loopback \n\n")
            fout.write("auto eth0 \n")
            fout.write("iface eth0 inet static \n")
            fout.write("\taddress 10.0.2.13 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.2.1 \n")
        if str(i) == "s4":
            fout.write("auto lo \n")
            fout.write("iface lo inet loopback \n\n")
            fout.write("auto eth0 \n")
            fout.write("iface eth0 inet static \n")
            fout.write("\taddress 10.0.2.14 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.2.1 \n")
        if str(i) == "s5":
            fout.write("auto eth0 \n")
            fout.write("iface eth0 inet static \n")
            fout.write("\taddress 10.0.2.15 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.2.1 \n")
        if str(i) == "lb":
            fout.write("auto lo \n")
            fout.write("iface lo inet loopback \n\n")
            fout.write("auto eth0 eth1\n")
            fout.write("iface eth0 inet static \n")
            fout.write("\taddress 10.20.1.1 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.1.1 \n")
            fout.write("iface eth1 inet static \n")
            fout.write("\taddress 10.20.2.1 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.2.1 \n")
        if str(i) == "c1":
            fout.write("auto lo \n")
            fout.write("iface lo inet loopback \n\n")
            fout.write("auto eth0 \n")
            fout.write("iface eth0 inet static \n")
            fout.write("\taddress 10.20.1.2 \n")
            fout.write("\tnetmask 255.255.255.0 \n")
            fout.write("\tgateway 10.20.1.1 \n")
        fout.close()
        call(["sudo", "virt-copy-in", "-a", str(i) + ".qcow2", "interfaces", "/etc/network"])
        call(["rm","-f","interfaces"])
        #Configura la maquina lb para distribuir trafico
        if str(i) == "lb":
            #Saca de la MV el archivo haproxy
            call(["sudo", "virt-copy-out", "-a", str(i) + ".qcow2", "/etc/haproxy/haproxy.cfg", "."])
            call(["touch", "haproxy2.cfg"])
            fout = open("haproxy.cfg", "r")
            fin = open("haproxy2.cfg", "w")
            for line in fout:
                fin.write(line)
            fin.write("\nfrontend lb \n")
            fin.write("\tbind *:80\n")
            fin.write("\tmode http\n")
            fin.write("\tdefault_backend webservers\n")
            fin.write("\nbackend webservers\n")
            fin.write("\tmode http\n")
            fin.write("\tbalance roundrobin\n")
            for j in vms:
                if j == "s1":
                    fin.write("\tserver s1 10.20.2.101:80 check\n")
                if j == "s2":
                    fin.write("\tserver s2 10.20.2.102:80 check\n")
                if j == "s3":
                    fin.write("\tserver s3 10.20.2.103:80 check\n")
                if j == "s4":
                    fin.write("\tserver s4 10.20.2.104:80 check\n")
                if j == "s5":
                    fin.write("\tserver s5 10.20.2.105:80 check\n")
            fin.close()
            fout.close()


def start():
    logger.info('Empezando...')
    for i in servers_name:
        if i == num_servers:
            os.system('xterm -e “sudo virsh console '+i+'”&')
            break
        else:
            os.system('xterm -e “sudo virsh console '+i+'”&')

def stop():#done
    logger.info('Parando...')
    # Apaga las máquinas
    for i in servers_name:
        if i.index == num_servers:
            os.system('sudo virsh shutdown '+i)
            break
        else:
            os.system('sudo virsh shutdown '+i)
    os.system('sudo virsh shutdown lb')
    os.system('sudo virsh shutdown c1')

def destroy():#done
    logger.info('Eliminando...')
    # Apaga forzadamente las máquinas
    for i in servers_name:
        if i == servers_name[num_servers]:
            os.system('sudo virsh destroy '+i)
            os.system('rm '+i+'.xml')
            os.system('rm '+i+'.qcow2')
            break
        else:
            os.system('sudo virsh destroy '+i)
            os.system('rm '+i+'.xml')
            os.system('rm '+i+'.qcow2')
    os.system('sudo virsh destroy lb')
    os.system('sudo virsh destroy c1')
    # Elimina los archivos creados por el script      
    os.system('rm lb.xml')
    os.system('rm c1.xml')
    os.system('rm lb.qcow2')
    os.system('rm c1.qcow2')
    os.system('rm gestiona-pc1.json')

def help():
    print('Hoja de ayuda:')
    print('gestiona-pc1.py [param1] [param2]')
    print('\n\tparam1')
    print('\t|')
    print('\t -> prepare: preparacion para el script. Es obligatorio definir el nº de servidores que se requieren,')
    print('\t\t de lo contratio se pondrán dos por defecto')
    print('\t|')
    print('\t -> create: para crear los ficheros .qcow2 de diferencias y los de especificación en XML de cada MV,')
    print('\t así como los bridges virtuales que soportan las LAN del escenario')
    print('\t|')
    print('\t -> start: para arrancar las máquinas virtuales y mostrar su consola')
    print('\t|')
    print('\t -> stop: para parar las máquinas virtuales (sin liberarlas)')
    print('\t|')
    print(
        '\t -> destroy: para liberar el escenario, borrando todos los ficheros creados')
    print('\n\tparam2 (opcional)')
    print('\t|')
    print('\t -> número de servidores web a arrancar. Configurable de 1 a 5. Por defecto se asigna 2')

# @main
if len(sys.argv) >= 2:
    param1 = str(sys.argv[1])

    cont = 0
    for i in servers_name:
        if cont <= num_servers:
            vms.append(i)
            cont=cont+1
        else:
            vms.append(i)
            break
    print(vms)
    
# Si debugmode es true, se ejecuta el debuger
    if debugmode:
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger('gestiona-pc1')
    else:
        logging.basicConfig(level=logging.INFO)
        logger = logging.getLogger('gestiona-pc1')

    list_qcow2 = subprocess.run(
        ["ls", "/lab/cdps/pc1/cdps-vm-base-pc1.qcow2"], stdout=open(os.devnull, 'wb'), stderr=STDOUT)
    # Buscamos que la imagen de la VM se encuentre en el directorio
    if list_qcow2.returncode:   # Si el comando list_qcow2 devuelve 1 -> NO se ha encontrado el archivo
        logger.info('\nNo se encuentra el archivo cdps-vm-base-pc1.qcow2')
        logger.info('Se procede a su descarga...\n')
        #os.system('wget https://idefix.dit.upm.es/download/cdps/pc1/cdps-vm-base-pc1.qcow2')

    if sys.argv[1] == 'create' and len(sys.argv) == 2:
        create()
    elif sys.argv[1] == 'start' and len(sys.argv) == 2:
        start()
    elif sys.argv[1] == 'stop' and len(sys.argv) == 2:
        stop()
    elif sys.argv[1] == 'destroy' and len(sys.argv) == 2:
        destroy()
    elif sys.argv[1] == 'prepare':
        prepare()
    else:
        help()
else:
    print("\nAlgo no ha salido bien")
    print("Algún parámetro es incorrecto o está fuera de los límites\n")
    print('Para ver la hoja de ayudas:')
    print('\t$gestiona-pc1.py help')