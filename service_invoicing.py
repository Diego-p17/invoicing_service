import  logging
import  time
import  json
import  os
import  base64
import  traceback

from    datetime  import datetime
from    time      import sleep

class Service_invoicing:

    def __init__(self):
        logging.info(f"INIT CLASS ({self.__class__.__name__})")

    def start(self,dataPath,dataConfig, idDevice, saveBilling = None, mqtt = None, topic = None)-> bool:
        logging.info(f"------------------------------------------------")
        logging.info(f"             INICIANDO FACTURADOR               ")
        logging.info(f"------------------------------------------------")

        try:
            self._mqtt           = mqtt
            self.topic           = topic
            self.dataPath        = dataPath
            self.dataConfig      = dataConfig
            self.saveBilling     = saveBilling
            self.idDevice        = idDevice
            self.dataGovernor    = ""

            self.getSettings()
            self.updateResolution()

            return True

        except Exception as e:
            error = str(e) + ": " + traceback.format_exc()
            logging.info(f"Ha Ocurrido un error al iniciar el facturador -----> {error}")
            return False

    def getSettings(self)-> None:

        self.controlShift    = f"{self.dataPath}shiftControl/controlShift.json"
        self.nextInvoice     = f"{self.dataPath}shiftControl/nextInvoice.json"
        self.currency_symbol = self.dataConfig.get("Currency_symbol", "$")

        if not self.saveBilling : self.saveBilling = f"{self.dataPath}transactions/trans/"

        #*Get Resolution
        try:
            url_shiftResult = self.dataPath + "shiftControl/"
            if not os.path.isdir(url_shiftResult): os.makedirs(url_shiftResult)

            if not os.path.exists(self.nextInvoice): logging.info("No se encuentra el archivo de resolucion local")
            else:
                with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                file.close()

        except Exception as e:
            error = str(e) + ": " + traceback.format_exc()
            logging.info(f"Error al cargar los datos de la resolucion: {error}")

    # GESTOR FACTURACION
    def invoice(self, dataInvoice:dict, typeInvoice = 2 , printer = "dict") -> dict:
        self.getSettings()
        def createInvoice():

            logging.info("--------------------------------------------------------------------")
            logging.info("                       GENERANDO FACTURA                            ")
            logging.info("--------------------------------------------------------------------")

            try:
                #* Get Data Shift
                with open(self.controlShift) as file: data_turn = json.load(file)
                file.close()

                self. id_shift = data_turn["Id_Shift"]
                dateBilling    = datetime.now()
                epoch          = int(datetime.timestamp(dateBilling)*1)

                # CREATE INVOICE
                generic_Invoice = {}
                generic_Invoice["JsonType"]          = int(typeInvoice)
                generic_Invoice["DateNow"]           = int(datetime.timestamp(dateBilling))
                generic_Invoice["IdInvoice"]         = self.resolution["actualIndexResolution"]
                generic_Invoice["IdDevice"]          = self.idDevice
                generic_Invoice["IdShift"]           = self.id_shift
                generic_Invoice["Id_Transaction"]    = f'{self.idDevice}-{epoch}'
                generic_Invoice["InvoiceDate"]       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                generic_Invoice["numResolution"]     = self.resolution["numResolution"]
                generic_Invoice["Prefix"]            = self.resolution["prefijo"]
                generic_Invoice["TotalWithoutTaxes"] = 0
                generic_Invoice["TotalTaxes"]        = 0
                generic_Invoice["Subtotal"]          = 0
                generic_Invoice["TotalAdjustments"]  = 0
                generic_Invoice["Total"]             = 0
                generic_Invoice["isVoided"]          = False
                generic_Invoice["IsElectronic"]      = False
                generic_Invoice["Tax"]               = dataInvoice["Tax"]
                generic_Invoice["items"]             = []
                generic_Invoice["PaymentMethod"]     = dataInvoice["PaymentMethod"]
                generic_Invoice["PaymentDetails"]    = dataInvoice["PaymentDetails"]
                generic_Invoice["Receipt"]           = ""
                generic_Invoice["Note"]              = ""
                generic_Invoice["ElectronicData"]    = {}
                generic_Invoice["epoch"]             = epoch
                generic_Invoice["TotalItems"]        = {}

                #* ADD ITEMS
                if dataInvoice["items"]:

                    TotalWithoutTaxes = 0
                    totalTaxes        = 0
                    totalsubtotal     = 0
                    totalAdjustment   = 0
                    totalInvoice      = 0

                    taxes = generic_Invoice["Tax"]
                    for item in dataInvoice["items"]:
                        totalItem          = taxCalculator(item, taxes)

                        TotalWithoutTaxes += totalItem["TotalWithoutTaxes"]
                        totalTaxes        += totalItem["tax"]
                        totalsubtotal     += totalItem["Subtotal"]
                        totalAdjustment   += abs(totalItem["TotalAdjustment"])
                        totalInvoice      += totalItem["Total"]

                        if "AgreementsApplied" in item: totalItem["AgreementsApplied"]  = item["AgreementsApplied"]
                        if "ParkingData"       in item: totalItem["ParkinData"]         = item["ParkingData"]
                        if "NoteItems"         in item: totalItem["NoteItems"]          = item["NoteItems"]

                        if "TypeItem" in item :

                            if item["TypeItem"] == 1:
                                if "Carro" in generic_Invoice["TotalItems"]:
                                    generic_Invoice["TotalItems"]["Carro"] += totalItem["Total"]
                                else:
                                    generic_Invoice["TotalItems"]["Carro"] = 0
                                    generic_Invoice["TotalItems"]["Carro"] += totalItem["Total"]
                            elif item["TypeItem"] == 2:
                                if "Moto" in generic_Invoice["TotalItems"]:
                                    generic_Invoice["TotalItems"]["Moto"] += totalItem["Total"]
                                else:
                                    generic_Invoice["TotalItems"]["Moto"] = 0
                                    generic_Invoice["TotalItems"]["Moto"] += totalItem["Total"]
                            elif item["TypeItem"] == 3:
                                if "Placa" in generic_Invoice["TotalItems"]:
                                    generic_Invoice["TotalItems"]["Placa"] += totalItem["Total"]
                                else:
                                    generic_Invoice["TotalItems"]["Placa"] = 0
                                    generic_Invoice["TotalItems"]["Placa"] += totalItem["Total"]

                        else:
                            if "Productos" in generic_Invoice["TotalItems"]:
                                generic_Invoice["TotalItems"]["Productos"] += totalItem["Total"]
                            else:
                                generic_Invoice["TotalItems"]["Productos"] = 0
                                generic_Invoice["TotalItems"]["Productos"] += totalItem["Total"]

                        generic_Invoice["items"].append(totalItem)

                    generic_Invoice["TotalWithoutTaxes"]   = TotalWithoutTaxes
                    generic_Invoice["TotalTaxes"]          = totalTaxes
                    generic_Invoice["Subtotal"]            = totalsubtotal
                    generic_Invoice["TotalAdjustments"]    = totalAdjustment
                    generic_Invoice["Total"]               = totalInvoice
                    generic_Invoice["Reference"]           = {"Id_TransactionParent": generic_Invoice["Id_Transaction"] }

                    if "Note" in dataInvoice            : generic_Invoice["Note"]           = dataInvoice["Note"]
                    if "Reference" in dataInvoice       : generic_Invoice["Reference"]      = dataInvoice["Reference"]
                    if "ElectronicData" in dataInvoice  : generic_Invoice["ElectronicData"] = dataInvoice["ElectronicData"]
                    if "Details" in dataInvoice         : generic_Invoice["Details"]        = dataInvoice["Details"]
                else:

                    logging.info("---------------------------------------------")
                    logging.info("----> No se puede facturar sin items")
                    logging.info("---------------------------------------------")

                checkResolution = self.checkResolution()

                if checkResolution:
                    logging.info("----> Resolucion valida")

                    with open(self.nextInvoice) as file: resolution = json.load(file)
                    file.close()

                    resolution["actualIndexResolution"] = int(resolution["actualIndexResolution"]) + 1
                    with open(self.nextInvoice, 'w') as file: json.dump(resolution, file, indent=4)
                    file.close()

                    logging.info(f"----> Factura Generada")
                    logging.info(generic_Invoice)

                    return generic_Invoice

                else:
                    logging.info("----> Resolucion invalida")
                    logging.info("----> Factura no fue generada")
                    return False

            except Exception as e:
                error = str(e) + ": " + traceback.format_exc()
                logging.info(f"Ha Ocurrido un error al iniciar el Crear Factura -----> {error}")
                return False

        def formatInvoice(invoice):
            # TEMPLATE INVOICE
            """
                @Empresa\n
                @Direccion\n
                @Telefono\n
                NIT: @Nit\n\n\n
                Formulario No: @ResDIAN\n
                FECHA @FechaDIAN hasta @FechaEndDIAN\n
                RANGO DE FACTURACION PREFIJO @IdTerminal\n
                Desde @ResINI hasta @ResFIN\n\n
                Transaccion: @TransaccionId\n\n
                --------------------------------------------\n
                Sistema POS No:      @Recibo\n
                Fecha de expedicion: @FechaRecibo\n
                --------------------------------------------\n
                @Detalles\n
                --------------------------------------------\n

                Detalle          Subtotal   impuesto   Total\n
                --------------------------------------------\n
                @DatosFactura\n
                        SUB TOTAL:       @Moneda @SinImpuestoTotal\n
                        Impuesto :       @Moneda @ImpuestoTotal\n
                                        ------------------\n
                        Total:           @Moneda @Total\n
                        Ajuste:          @Moneda @AjusteAntes\n
                                        ------------------\n\n
                        TOTAL A PAGAR:   @Moneda @ValorTotal\n
                --------------------------------------------\n
                Pago @TipoPago\n
                @DataAux\n
                --------------------------------------------\n
                @Footer
            """

            strInvoice = "@Empresa\n@Direccion\n@Telefono\nNIT: @Nit\n\n\nFormulario No: @ResDIAN\nFECHA @FechaDIAN hasta @FechaEndDIAN\nRANGO DE FACTURACION PREFIJO @IdTerminal\nDesde @ResINI hasta @ResFIN\n\nTransaccion: @TransaccionId\n\n--------------------------------------------\nSistema POS No:      @Recibo\nFecha de expedicion: @FechaRecibo\n--------------------------------------------\n@Detalles\n--------------------------------------------\nDetalle          Subtotal   impuesto   Total\n--------------------------------------------\n@DatosFactura\n\n        SUB TOTAL:       @Moneda @SinImpuestoTotal\n        Impuesto :       @Moneda @ImpuestoTotal\n                        ------------------\n        Total:           @Moneda @Total\n        Ajuste:          @Moneda @AjusteAntes\n                        ------------------\n\n        TOTAL A PAGAR:   @Moneda @ValorTotal\n--------------------------------------------\nPago @TipoPago\n@DataAux\n--------------------------------------------\n@Footer"

            #* Aditional Info
            extraItems = ""
            if "Details" in invoice:
                for key, value in invoice["Details"].items():
                    key = key + ":"
                    key = key.ljust(19, " ")
                    extraItems += f"{key}{value}\n"
                invoice.pop("Details")

            #* List Products
            acu = 0
            listDetails = ""
            listItems   = ""
            if invoice["items"]:
                for item in invoice["items"]:
                    detailItems = ""
                    for value in item.values():
                        acu += 1
                        if acu > 1 and acu < 6:
                            detailItems += f"{value}   "

                    listItems += detailItems + "\n"
                    acu = 0

            else: listItems = "Sin Productos"

            #* DataAux Type Payment
            formatDataAux = {}
            if invoice["PaymentMethod"]   ==  0 : #*EFECTIVO
                typePayment = "Efectivo"
                formatDataAux["Efectivo"]        = invoice["PaymentDetails"]["valuePaid"]
                formatDataAux["Cambio"]          = invoice["PaymentDetails"]["change"]
                formatDataAux["Dinero Faltante"] = invoice["PaymentDetails"]["notDispense"]

            elif invoice["PaymentMethod"] ==  1 : #*CARD
                typePayment = "Tarjeta"
                formatDataAux["Cuotas"]          = invoice["PaymentDetails"]["dues"]
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["cardAuthCode"]
                formatDataAux["Franquicia"]      = invoice["PaymentDetails"]["franchise"]
                formatDataAux["ultimos4"]        = invoice["PaymentDetails"]["last4Number"]
                formatDataAux["tipo"]            = invoice["PaymentDetails"]["accountType"]

            elif invoice["PaymentMethod"] ==  2 : #*MAGNETIC CARD
                typePayment = "MagneticCard"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]


            elif invoice["PaymentMethod"] ==  3 : #*FLYPASS
                typePayment = "Flypass"
                invoice["PaymentDetails"] = ""

            elif invoice["PaymentMethod"] ==  4 : #*NEQUI
                typePayment = "Nequi"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]

            elif invoice["PaymentMethod"] ==  5 : #*BANCOLOMBIA
                typePayment = "Bancolombia"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]

            elif invoice["PaymentMethod"] ==  6 : #*RAPPI
                typePayment = "RappiPay"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]

            elif invoice["PaymentMethod"] ==  7 : #* TRANSFER
                typePayment = "Trasnfererencia"
                formatDataAux["Autorizacion"]    = invoice["PaymentDetails"]["autorization"]
                formatDataAux["Estatus"]         = invoice["PaymentDetails"]["status"]

            else:
                typePayment = "Desconocido"
                invoice["PaymentDetails"] = ""

            dataAux = ""
            if invoice["PaymentDetails"]:
                    dataAux = ""
                    for key, value in formatDataAux.items():
                        key = key + ":"
                        key = key.ljust(19, " ")
                        dataAux += f"{key}$ {value}\n"

            data_template = self.dataConfig["template_invoice"]

            # Data Enterprise
            strInvoice = strInvoice.replace("@Empresa", data_template["enterprise"])
            strInvoice = strInvoice.replace("@Direccion", data_template["address"])
            strInvoice = strInvoice.replace("@Telefono", data_template["cellphone"])
            strInvoice = strInvoice.replace("@Nit", data_template["nit"])

            # HEADER
            resolution =  self.resolution
            strInvoice = strInvoice.replace("@ResDIAN", resolution["numResolution"])
            strInvoice = strInvoice.replace("@FechaDIAN", str(resolution["startDate"]))
            strInvoice = strInvoice.replace("@FechaEndDIAN", str(resolution["endDate"]))
            strInvoice = strInvoice.replace("@IdTerminal", resolution["prefijo"])
            strInvoice = strInvoice.replace("@ResINI", str(resolution["startNumber"]))
            strInvoice = strInvoice.replace("@ResFIN", str(resolution["endNumber"]))
            strInvoice = strInvoice.replace("@Recibo", str(resolution["prefijo"]) + "-" + str(invoice["IdInvoice"]))
            strInvoice = strInvoice.replace("@FechaRecibo", str(invoice["InvoiceDate"]))
            strInvoice = strInvoice.replace("@TransaccionId", invoice["Id_Transaction"])

            #ITEMS DESCRIPTION
            strInvoice = strInvoice.replace("@Detalles", str(extraItems))
            strInvoice = strInvoice.replace("@DetailsParking", str(listDetails))
            strInvoice = strInvoice.replace("@DatosFactura", str(listItems))

            # DATA PAYMENT
            strInvoice = strInvoice.replace("@Moneda",str(self.currency_symbol))
            strInvoice = strInvoice.replace("@Total",str(round(invoice["Total"])))
            strInvoice = strInvoice.replace("@AjusteAntes",str(round(invoice["TotalAdjustments"])))
            strInvoice = strInvoice.replace("@SinImpuestoTotal",str(round(invoice["TotalWithoutTaxes"] )))
            # strInvoice = strInvoice.replace("@IVA",str(invoice["taxValue"]))
            strInvoice = strInvoice.replace("@ImpuestoTotal", str(round(invoice["TotalTaxes"])))
            strInvoice = strInvoice.replace("@ValorTotal",  str(round(invoice["Subtotal"])))

            #INFORMATION AUX
            strInvoice = strInvoice.replace("@TipoPago",str(typePayment))
            strInvoice = strInvoice.replace("@DataAux",str(dataAux))

            # FOOTER
            if "footer" in data_template: strInvoice = strInvoice.replace("@Footer",data_template["footer"])
            else: strInvoice = strInvoice.replace("@Footer","")

            invoice["Receipt"] = strInvoice
            Invoice_bytes      = strInvoice.encode()
            Invoice_Base64     = base64.b64encode(Invoice_bytes)
            invoice_decode     = base64.b64decode(Invoice_Base64)

            logging.info(strInvoice)
            self.addInvoiceTurn(invoice)

            if   printer == "dict": return invoice
            elif printer == "pdf":  return Invoice_Base64
            else:                   return invoice

        def taxCalculator(item:dict, taxes:list):

            totaltaxes = 0
            if item["taxes"]:
                for idtaxes in item["taxes"]:
                    for taxinfo in taxes:
                        if taxinfo["Id_Tax"] == idtaxes:
                            totaltaxes += taxinfo["TaxValue"]
                            break

            if not item["include"]:
                TotalWithoutTaxes = item["Total"]
                tax   = (item["Total"] * totaltaxes) / 100
                total = item["Total"] + tax

            else:
                total = item["Total"]
                totaltaxes = (totaltaxes / 100) + 1
                TotalWithoutTaxes  = round(total / totaltaxes, 2)
                tax   = round(total - TotalWithoutTaxes, 2)

            if item["Total"] == 1:
                totalRound      = item["Total"]
                totalAdjustment = 0
                total           = item["Total"]
            else:
                adjustment      = self.dataConfig["adjustment"]
                totalRound      = total / adjustment
                totalRound      = round(totalRound) * adjustment
                totalAdjustment = totalRound - total

            description = item["description"]
            return {
                    "Id_Product": item["Id_Product"],
                    "description": description,
                    "TotalWithoutTaxes": TotalWithoutTaxes,
                    "tax": tax,
                    "Subtotal": totalRound,
                    "TotalAdjustment": abs(totalAdjustment),
                    "Total": total
                    }

        checkTurn = self.checkTurn()

        if checkTurn:
            invoice = createInvoice()
            if invoice:
                invoiceFormat  = formatInvoice(invoice)
                return invoiceFormat
            else:
                logging.info("No se ha podido generar la Factura")
                return False
        else:
            return False

    #GESTOR TURNOS
    def checkTurn(self) -> bool:
        try:
            state = False
            logging.info("--------------------------------------------------------------------------------")
            logging.info("                           Obteniendo status de turno                           ")
            logging.info("--------------------------------------------------------------------------------")

            """ Validacion de turno abierto y obtencion del ID del turno abierto """
            idShift     = None
            infoMessage = "Error obteniendo id de turno"

            if not os.path.exists(self.controlShift):
                logging.info("--> Turno no existente")
                logging.info("--> Creando archivo de control ...")

                controlShift = self.generateTemplateTurn()
                if self.dataGovernor:
                    if self.dataGovernor.get("Shift") == None:  self.dataGovernor["Shift"] = 0
                    controlShift["Id_Shift"] = self.dataGovernor.get("Shift")

                else:
                    self.dataGovernor = self.configService()
                    controlShift["Id_Shift"]   = self.dataGovernor.get("Shift")

                controlShift["NextIdShift"]      = controlShift["Id_Shift"] + 1
                controlShift["InternalControl"]  = controlShift["InitialCash"]
                controlShift["Status"]           = 1

                with open(self.controlShift,'w') as createTurn: json.dump(controlShift, createTurn, indent= 4)
                createTurn.close()

                idShift = controlShift["Id_Shift"]

            else:
                with open(self.controlShift) as turn: currentShift = json.load(turn)

                if currentShift.get("Status") == 0:
                    idShift     = currentShift["Id_Shift"]
                    infoMessage = f"Turno obtenido exitosamente: ID-{idShift}"
                    state       = True

                else:
                    infoMessage = "Turno cerrado, por favor abrir turno"

            logging.info("--------------------------------------------------------------------------------")
            logging.info(f"Respuesta del status del turno: {infoMessage}")
            logging.info("--------------------------------------------------------------------------------")

        except Exception as e:
            error = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error chequeando turno: {error}")

        finally: return state

    def openTurn(self, content:dict, idShift = None)-> dict:
        self.getSettings()
        response          = False
        invoiceOpenShift  = ""

        try:
            if not content:content =  {"Id_People": 0 , "InitialCash": 0}
            if not isinstance(content["InitialCash"],int): raise Exception("Monto inicial debe ser numerico")

            checkResolution, message = self.checkResolution()

            if checkResolution:
                logging.info("--------------------------------------------------------------------")
                logging.info("                           Abriendo turno                           ")
                logging.info("--------------------------------------------------------------------")
                logging.info(f"Datos para abrir turno: {content}")

                #* CHECK FILES IN APP
                url_ControlShift  = f"{self.dataPath}shiftControl/"
                if not os.path.isdir(url_ControlShift): os.makedirs(url_ControlShift)

                if os.path.exists(self.controlShift):
                    with open(self.controlShift) as file: controlShift = json.load(file)
                    file.close()

                if controlShift.get("Status") == 0 :

                    if self.dataGovernor:
                        if self.dataGovernor.get("Shift") == None : self.dataGovernor["Shift"] = 0
                        if controlShift.get("Id_Shift") < self.dataGovernor.get("Shift") :
                            logging.info("Turno desactualizado, Creando un nuevo turno")

                            dataturn = self.generateTemplateTurn()
                            dataturn["Id_Shift"]         = self.dataGovernor.get("Shift", 1) + 1
                            dataturn["NextIdShift"]      = dataturn["Id_Shift"] + 1

                            with open(self.controlShift,'w') as createTurn: json.dump(dataturn, createTurn, indent= 4)
                            createTurn.close()

                            self.id_shift = dataturn["Id_Shift"]
                            self.backupTurn(self.id_shift)
                            response = True

                    else :
                        currentShift      = "Ya existe un turno Abierto"
                        self.idPeopleTurn = controlShift["Id_PeopleOpening"]

                else :
                    # !JSON CONTROL INTERNAL SHIFTS
                    logging.info("Abriendo turno")
                    currentShift = self.generateTemplateTurn()

                    if self.dataGovernor:
                        if not self.dataGovernor.get("Shift"):
                            currentShift["Id_Shift"]         = controlShift["NextIdShift"]
                            currentShift["NextIdShift"]      = controlShift["NextIdShift"] + 1

                        elif controlShift.get("Id_Shift") < self.dataGovernor.get("Shift") :

                            currentShift["Id_Shift"]         = self.dataGovernor.get("Shift") + 1
                            currentShift["NextIdShift"]      = controlShift["Id_Shift"] + 1
                        else:
                            currentShift["Id_Shift"]         = controlShift["NextIdShift"]
                            currentShift["NextIdShift"]      = controlShift["NextIdShift"] + 1
                    else:
                            currentShift["Id_Shift"]         = controlShift["NextIdShift"]
                            currentShift["NextIdShift"]      = controlShift["NextIdShift"] + 1

                    currentShift["Id_PeopleOpening"] = content.get("Id_People", 0)
                    currentShift["InitialCash"]      = content.get("InitialCash", 0)
                    currentShift["InternalControl"]  = currentShift["InitialCash"]

                    self.id_shift     = currentShift["Id_Shift"]
                    self.idPeopleTurn = currentShift["Id_PeopleOpening"]

                    with open(self.controlShift,'w') as createTurn: json.dump(currentShift, createTurn, indent= 4)
                    createTurn.close()


                    # !Generate Invoice OpenShift
                    """
                    @Empresa\n
                    @Direccion\n
                    @Telefono\n
                    NIT: @Nit\n\n\n
                    ID Turno:    @TurnoId\n
                    ID Apertura: @AperturaId\n
                    --------------------------------------------\n
                    @DataAux\n
                    --------------------------------------------\n
                    Fecha Apertura:      @FechaApertura\n
                    Factura Inicio:      @FacturaInicio\n\n
                    Monto Inicial:       @Moneda @MontoInicial\n
                    --------------------------------------------\n\n\n
                    """
                    templateInvoice = "@Empresa\n@Direccion\n@Telefono\nNIT: @Nit\n\n\nID Turno:    @TurnoId\nID Apertura: @AperturaId\n--------------------------------------------\n@DataAux\n--------------------------------------------\nFecha Apertura:      @FechaApertura\nFactura Inicio:      @FacturaInicio\n\nMonto Inicial:       @Moneda @MontoInicial\n--------------------------------------------\n\n\n"

                    enterprise = self.dataConfig["template_invoice"]

                    invoiceOpenShift = templateInvoice
                    invoiceOpenShift = invoiceOpenShift.replace("@Empresa", enterprise["enterprise"])
                    invoiceOpenShift = invoiceOpenShift.replace("@Direccion", enterprise["address"])
                    invoiceOpenShift = invoiceOpenShift.replace("@Telefono", enterprise["cellphone"])
                    invoiceOpenShift = invoiceOpenShift.replace("@Nit", enterprise["nit"])

                    invoiceOpenShift = invoiceOpenShift.replace("@DataAux", "Factura Apertura de Turno")
                    invoiceOpenShift = invoiceOpenShift.replace("@TurnoId", str(self.id_shift))
                    invoiceOpenShift = invoiceOpenShift.replace("@AperturaId", str(self.idPeopleTurn))
                    invoiceOpenShift = invoiceOpenShift.replace("@FechaApertura", str(currentShift["InitialDate"]))
                    invoiceOpenShift = invoiceOpenShift.replace("@FacturaInicio", str(currentShift["InitInvoice"]))

                    invoiceOpenShift = invoiceOpenShift.replace("@Moneda",str(self.currency_symbol))
                    invoiceOpenShift = invoiceOpenShift.replace("@MontoInicial", str(round(currentShift["InitialCash"])))


                    response = True

                    # !JSON SEND OPENSHIFT
                    openTurn = {}
                    #* DATA OpenTurn
                    openTurn["JsonType"]     = 3
                    openTurn["Id_Device"]    =  int(self.idDevice)
                    openTurn["Id_Shift"]     =  int(currentShift["Id_Shift"])
                    openTurn["Id_People"]    =  content["Id_People"]
                    openTurn["InitialCash"]  =  content["InitialCash"]
                    openTurn["FinalCash"]    =  0
                    openTurn["InvoiceCount"] =  0
                    openTurn["InvoiceTotal"] =  0
                    openTurn["InitialDate"]  =  str(currentShift["InitialDate"] )
                    openTurn["Receipt"]      =  str(invoiceOpenShift)
                    openTurn["OpenShift"]    =  True

                    nameShift = f"shiftResult-{int(time.time()*1000)}"
                    with open(self.saveBilling + str(nameShift) + '.json','w') as sendInvoice: json.dump(openTurn, sendInvoice, indent= 4)
                    sendInvoice.close()

                    self.backupTurn(self.id_shift)
                    Invoice_bytes  = invoiceOpenShift.encode()
                    Invoice_Base64 = base64.b64encode(Invoice_bytes)
                    logging.info(invoiceOpenShift)
            else:
                response         = checkResolution
                invoiceOpenShift = message
        except Exception as e:
            currentShift     = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error abriendo turno: {currentShift}")

        finally:
            return response,invoiceOpenShift

    def closeTurn(self, content:dict)->str:
        """ Funcion para cerrar turno """
        retorno = False
        try:
            if not content: content =  {"Id_People": 0 , "FinalCash": 0}
            logging.info("--------------------------------------------------------------------")
            logging.info("                           Cerrando turno                           ")
            logging.info("--------------------------------------------------------------------")
            logging.info(f"Datos de usuario que cierra turno: {content}")

            #*get Data from "Turn"
            with open(self.controlShift) as dataTurn: turn = json.load(dataTurn)
            dataTurn.close()

            if turn["Status"] == 1:
                message = "EL TURNO YA FUE CERRADO"
                invoiceCloseShift = ""
            else:
                # diference = totalCash - turn["InternalControl"]
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                turn["Id_PeopleClosed"] = content["Id_People"]
                turn["FinishInvoice"]   = self.resolution["actualIndexResolution"]
                #turn["Diference"]       = diference
                turn["FinalCash"]       = content["FinalCash"]
                turn["FinalDate"]       = str(timestamp)
                turn["Status"]          = 1
                totalCash               = turn["FinalCash"] + turn["StackControl"]


                with open(self.controlShift, 'w', encoding='utf-8') as file: json.dump(turn, file, indent=2)
                file.close()

                id_shift        = str(turn['Id_Shift'])
                url_shiftResult = self.dataPath + "shiftControl/shiftResults/" + id_shift

                if not os.path.isdir(url_shiftResult): os.makedirs(url_shiftResult)

                if os.path.isdir( f"{url_shiftResult}" ):
                    nameShift = f"shiftResult-{id_shift}.json"
                    with open(url_shiftResult + '/'+ nameShift, 'w', encoding='utf-8') as file: json.dump(turn, file, indent=4)
                    file.close()

                # !Generate Invoice CloseShift
                """
                @Empresa\n@Direccion\n@Telefono\n
                NIT: @Nit\n\n\n
                --------------------------------------------\n
                @DataAux\n
                --------------------------------------------\n
                ID Turno:             @IDTurno\n
                ID Apertura:          @IDApertura\n
                ID Cierre:            @IDCierre\n
                --------------------------------------------\n
                Fecha Apertura:       @FechaApertura\n
                Fecha Cierre:         @FechaCierre\n\n
                --------------------------------------------\n
                Factura Inicio:       @FacturaInicio\n
                Factura Final:        @FacturaFinal\n
                Total Facturas:       @TotalFacturas\n
                --------------------------------------------\n
                Base(Efectivo):       @Moneda @MontoInicial\n
                Recargas:             @Moneda @Recargas\n
                Retiros:              @Moneda @Vaciados\n
                Fallos al devolver:   @Moneda @FallosAlDevolver\n
                Efectivo Facturado:   @Moneda @Cash\n
                Efectivo Total:       @Moneda @ControlInterno\n
                --------------------------------------------\n
                Detalle de Pagos\n
                --------------------------------------------\n
                @PayDetails
                                    ----------------------\n
                Total Facturado:      @Moneda @Total\n
                --------------------------------------------\n
                Detalle de Productos Facturados\n
                --------------------------------------------\n
                @TypeItem
                Total Facturado  :      @Moneda @Total\n
                """
                # templateInvoice = "@Empresa\n@Direccion\n@Telefono\nNIT: @Nit\n\nID Turno:    @IDTurno\nID Apertura: @IDApertura\nID Cierre:   @IDCierre\n--------------------------------------------\nFecha Apertura:        @FechaApertura\nFecha Cierre:          @FechaCierre\n\nFactura Inicio:        @FacturaInicio\nFactura Final:         @FacturaFinal\nTotal Facturas:        @TotalFacturas\n--------------------------------------------\nDescripcion\n--------------------------------------------\nMonto Inicial:        @Moneda @MontoInicial\nMonto Final:          @Moneda @MontoFinal\n--------------------------------------------\n@TypeItem--------------------------------------------\nBase:                 @Moneda @Stack\nDepositos:            @Moneda @Recargas\nRetiros:              @Moneda @Vaciados\nFallos al devolver:   @Moneda @FallosAlDevolver\n--------------------------------------------\nEfectivo:             @Moneda @Cash\nTarjeta:              @Moneda @TarjetaPago\nRappi:                @Moneda @RappiPago\nMagnetica:            @Moneda @MagneticCard\nFlypass:              @Moneda @FlypassPago\nNequi:                @Moneda @NequiPago\nBancolombia:          @Moneda @Bancolombia\nTransferencia:        @Moneda @Trasferencia\n--------------------------------------------\nEfectivo Caja:        @Moneda @EfectivoCaja\nRecaudo:              @Moneda @ControlInterno\n                    --------------------   \nDiferencia:           @Moneda @Diferencia\n\nTotal impuestos:      @Moneda @TotalImpuestos\nSubTotal:             @Moneda @SubTotal\nTOTAL PAGOS:          @Moneda @Total\n--------------------------------------------\n@DataAux\n--------------------------------------------\n"
                templateInvoice = "@Empresa\n@Direccion\n@Telefono\nNIT: @Nit\n\n\n--------------------------------------------\n@DataAux\n--------------------------------------------\nID Turno:             @IDTurno\nID Apertura:          @IDApertura\nID Cierre:            @IDCierre\n--------------------------------------------\nFecha Apertura:       @FechaApertura\nFecha Cierre:         @FechaCierre\n\n--------------------------------------------\nFactura Inicio:       @FacturaInicio\nFactura Final:        @FacturaFinal\nTotal Facturas:       @TotalFacturas\n--------------------------------------------\nBase(Efectivo):       @Moneda @MontoInicial\nRecargas:             @Moneda @Recargas\nRetiros:              @Moneda @Vaciados\nFallos al devolver:   @Moneda @FallosAlDevolver\nEfectivo Facturado:   @Moneda @Cash\n                    ------------------------\n\nEfectivo Total:       @Moneda @ControlInterno\n--------------------------------------------\nDetalle de Pagos\n--------------------------------------------\n@PayDetails                    ----------------------\nTotal Facturado:      @Moneda @Total\n--------------------------------------------\nDetalle de Productos Facturados\n--------------------------------------------\n@TypeItem                    ------------------------\n\nTotal Facturado:      @Moneda @Total\n\n\n\n"
                enterprise = self.dataConfig["template_invoice"]

                invoiceCloseShift = templateInvoice
                invoiceCloseShift = invoiceCloseShift.replace("@Empresa", enterprise["enterprise"])
                invoiceCloseShift = invoiceCloseShift.replace("@Direccion", enterprise["address"])
                invoiceCloseShift = invoiceCloseShift.replace("@Telefono", enterprise["cellphone"])
                invoiceCloseShift = invoiceCloseShift.replace("@Nit", enterprise["nit"])

                invoiceCloseShift = invoiceCloseShift.replace("@DataAux", "Factura Cierre de Turno")

                invoiceCloseShift = invoiceCloseShift.replace("@IDTurno", str(turn["Id_Shift"]))
                invoiceCloseShift = invoiceCloseShift.replace("@IDApertura", str(turn["Id_PeopleOpening"]))
                invoiceCloseShift = invoiceCloseShift.replace("@IDCierre", str(turn["Id_PeopleClosed"]))

                invoiceCloseShift = invoiceCloseShift.replace("@FechaApertura", str(turn["InitialDate"]))
                invoiceCloseShift = invoiceCloseShift.replace("@FechaCierre", str(turn["FinalDate"]))

                invoiceCloseShift = invoiceCloseShift.replace("@FacturaInicio", str(turn["InitInvoice"]))
                invoiceCloseShift = invoiceCloseShift.replace("@FacturaFinal", str(turn["FinishInvoice"]))
                invoiceCloseShift = invoiceCloseShift.replace("@TotalFacturas", str(turn["TotalInvoices"]))

                invoiceCloseShift = invoiceCloseShift.replace("@Moneda", str(self.currency_symbol))
                invoiceCloseShift = invoiceCloseShift.replace("@MontoInicial", str(round(turn["InitialCash"])))
                invoiceCloseShift = invoiceCloseShift.replace("@Recargas", str(round(turn["Recharge"])))
                invoiceCloseShift = invoiceCloseShift.replace("@Vaciados", str(round(turn["Emptied"])))
                invoiceCloseShift = invoiceCloseShift.replace("@FallosAlDevolver", str(round(turn["FailReturn"])))
                #invoiceCloseShift = invoiceCloseShift.replace("@Cash", str(round(turn["MethodsPay"])))
                invoiceCloseShift = invoiceCloseShift.replace("@ControlInterno", str(round(totalCash)))
                invoiceCloseShift = invoiceCloseShift.replace("@Total", str(round(turn["TotalwhitTaxes"])))

                if "Efectivo" in turn["MethodsPay"]:
                    invoiceCloseShift = invoiceCloseShift.replace("@Cash", str(round(turn["MethodsPay"]["Efectivo"])))
                else:
                    invoiceCloseShift = invoiceCloseShift.replace("@Cash", str(0))
                if turn["MethodsPay"]:
                    payDetails = ""
                    for key, value in turn["MethodsPay"].items():
                        key = key + ":"
                        key = key.ljust(22, " ")
                        payDetails += f"{key}$ {value}\n"
                    invoiceCloseShift = invoiceCloseShift.replace("@PayDetails", str(payDetails))
                else:
                    invoiceCloseShift = invoiceCloseShift.replace("@PayDetails", "No se realizaron Pagos\n")

                if "TotalItems" in turn:
                    typeItems = ""
                    for key, value in turn["TotalItems"].items():
                        key = key + ":"
                        key = key.ljust(22, " ")
                        typeItems += f"{key}$ {value}\n"
                    invoiceCloseShift = invoiceCloseShift.replace("@TypeItem", str(typeItems))
                else:
                    invoiceCloseShift = invoiceCloseShift.replace("@TypeItem", str("No se realizaron Pagos\n"))

                # !JSON SEND CLOSE SHIFT
                closeTurn = {}
                #* DATA OpenTurn
                closeTurn["JsonType"] = 3
                closeTurn["Id_Device"]       =  int(turn["Id_Device"])
                closeTurn["Id_Shift"]        =  int(turn["Id_Shift"])
                closeTurn["Id_People"]       =  turn["Id_PeopleOpening"]
                closeTurn["InitialCash"]     =  turn["InitialCash"]
                closeTurn["FinalCash"]       =  turn["FinalCash"]
                closeTurn["InvoiceCount"]    =  turn["TotalInvoices"]
                closeTurn["InvoiceTotal"]    =  turn["TotalwhitTaxes"]
                closeTurn["InitialDate"]     =  turn["InitialDate"]
                closeTurn["FinalDate"]       =  turn["FinalDate"]
                closeTurn["Receipt"]         =  str(invoiceCloseShift)
                closeTurn["OpenShift"]       =  False

                # url_billings = f"{self.dataPath}transactions/trans/"
                if not os.path.isdir(self.saveBilling):
                    logging.info(" ERROR ---> No se encuentra la ruta para enviar la factura de cierre ")
                else:
                    nameShift = f"shiftResult-{int(time.time()*1000)}"
                    with open(self.saveBilling + str(nameShift) + '.json','w') as sendInvoice: json.dump(closeTurn, sendInvoice, indent= 4)
                    sendInvoice.close()

                retorno = True
                message = "TURNO CERRADO EXITOSAMENTE"
                logging.info(f"Respuesta al cerrar turno: {message}")
                logging.info(invoiceCloseShift)

                Invoice_bytes  = invoiceCloseShift.encode()
                Invoice_Base64 = base64.b64encode(Invoice_bytes)

        except Exception as e:
            currentShift     = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error cerrando turno: {currentShift}")
            invoiceCloseShift = ""
            retorno = False

        finally:
            return retorno,invoiceCloseShift

    def backupTurn(self,idShift:int)-> bool:
        """ Escribe el JSON del turno y lo guarda localmente """
        try:
            url_shiftResult = self.dataPath + "shiftControl/shiftResults/"
            if not os.path.exists(url_shiftResult): os.makedirs(url_shiftResult)

            shiftPackage = url_shiftResult + f"/{idShift}/"
            if not os.path.exists(shiftPackage ): os.makedirs(shiftPackage)

            logging.info("--------------------------------------------------------------------")
            logging.info("---> Creando Backup del turno")
            logging.info("--------------------------------------------------------------------")
            return True
        except Exception as e:
            logging.error(f"Error al Crear el Backup: {e}")
            return False

    def balanceTurn(self)->str:
        """ Funcion Obtener balance turno """
        retorno = False
        try:
            logging.info("-----------------------------------------------------------------------")
            logging.info("                           Balance del turno                           ")
            logging.info("-----------------------------------------------------------------------")

            #*get Data from "Turn"
            with open(self.controlShift) as dataTurn: turn = json.load(dataTurn)
            dataTurn.close()
            totalCash = turn["InternalControl"] + turn["StackControl"]

            if turn["Status"] == 1:
                message = "NO SE GENERA BALANCE,EL TURNO YA FUE CERRADO"
                retorno = False
                invoiceBalanceShift = ""
            else:

                # !Generate Invoice BalanceShift
                """
                --------------------------------------------\n
                BALANCE TURNO\n
                --------------------------------------------\n
                ID Turno:              @IDTurno\n
                Fecha Apertura:        @FechaApertura\n
                Factura Inicio:        @FacturaInicio\n
                Total Facturas:        @TotalFacturas\n
                --------------------------------------------\n
                Descripcion\n
                --------------------------------------------\n
                Monto Inicial:        @Moneda @MontoInicial\n
                Fallos Cambio:        @Moneda @FallosAlDevolver\n
                --------------------------------------------\n
                Efectivo:             @Moneda @EfectivoCaja\n
                Tarjeta:              @Moneda @TarjetaPago\n
                Rappi:                @Moneda @RappiPago\n
                Magnetica:            @Moneda @MagneticCard\n
                Flypass:              @Moneda @FlypassPago\n
                Nequi:                @Moneda @NequiPago\n
                Bancolombia:          @Moneda @Bancolombia\n
                Transferencia:        @Moneda @Trasferencia\n

                Control Interno:      @Moneda @ControlInterno\n
                                    --------------------   \n
                TOTAL PAGOS:          @Moneda @Total\n
                --------------------------------------------\n
                @DataAux\n
                --------------------------------------------\n
                """
                #templateInvoice = "--------------------------------------------\nBALANCE TURNO\n--------------------------------------------\nID Turno:              @IDTurno\nFecha Apertura:        @FechaApertura\nFactura Inicio:        @FacturaInicio\nTotal Facturas:        @TotalFacturas\n--------------------------------------------\nDescripciÃ³n\n--------------------------------------------\nMonto Inicial:        @Moneda @MontoInicial\nFallos Cambio:        @Moneda @FallosAlDevolver\n--------------------------------------------\nEfectivo:             @Moneda @EfectivoCaja\nTarjeta:              @Moneda @TarjetaPago\nRappi:                @Moneda @RappiPago\nMagnetica:            @Moneda @MagneticCard\nFlypass:              @Moneda @FlypassPago\nNequi:                @Moneda @NequiPago\nBancolombia:          @Moneda @Bancolombia\nTransferencia:        @Moneda @Trasferencia\nControl Interno:      @Moneda @ControlInterno\n                    --------------------   \nTOTAL PAGOS:          @Moneda @Total\n--------------------------------------------\n@DataAux\n--------------------------------------------\n"
                templateInvoice = "--------------------------------------------\nBALANCE TURNO\n--------------------------------------------\nID Turno:              @IDTurno\nFecha Apertura:        @FechaApertura\nFactura Inicio:        @FacturaInicio\nTotal Facturas:        @TotalFacturas\n--------------------------------------------\nDescripcion\n--------------------------------------------\nBase(Efectivo):       @Moneda @MontoInicial\nFallos al devolver:   @Moneda @FallosAlDevolver\nEfectivo Facturado:   @Moneda @Cash\n                    ---------------------\n\nEfectivo Total:       @Moneda @ControlInterno\n--------------------------------------------\nDetalle de Productos Facturados\n--------------------------------------------\n@TypeItem--------------------------------------------\nDetalle de Pagos\n--------------------------------------------\n@PayDetails                    --------------------\n\nTotal Facturado:      @Moneda @Total\n--------------------------------------------\n@DataAux\n--------------------------------------------\n"
                enterprise = self.dataConfig["template_invoice"]

                invoiceBalanceShift = templateInvoice
                invoiceBalanceShift = invoiceBalanceShift.replace("@IDTurno", str(turn["Id_Shift"]))
                invoiceBalanceShift = invoiceBalanceShift.replace("@FechaApertura", str(turn["InitialDate"]))
                invoiceBalanceShift = invoiceBalanceShift.replace("@FacturaInicio", str(turn["InitInvoice"]))
                invoiceBalanceShift = invoiceBalanceShift.replace("@TotalFacturas", str(turn["TotalInvoices"]))
                invoiceBalanceShift = invoiceBalanceShift.replace("@Moneda", str(self.currency_symbol))
                invoiceBalanceShift = invoiceBalanceShift.replace("@MontoInicial", str(round(turn["InitialCash"])))
                invoiceBalanceShift = invoiceBalanceShift.replace("@FallosAlDevolver", str(round(turn["FailReturn"])))


                invoiceBalanceShift = invoiceBalanceShift.replace("@ControlInterno", str(round(totalCash)))
                invoiceBalanceShift = invoiceBalanceShift.replace("@Total", str(round(turn["TotalwhitTaxes"])))
                invoiceBalanceShift = invoiceBalanceShift.replace("@DataAux", "Factura Balance de Turno")

                if "Efectivo" in turn["MethodsPay"]:
                    invoiceBalanceShift = invoiceBalanceShift.replace("@Cash", str(round(turn["MethodsPay"]["Efectivo"])))
                else:
                    invoiceBalanceShift = invoiceBalanceShift.replace("@Cash", str(0))
                if turn["MethodsPay"]:
                    payDetails = ""
                    for key, value in turn["MethodsPay"].items():
                        key = key + ":"
                        key = key.ljust(22, " ")
                        payDetails += f"{key}$ {value}\n"
                    invoiceBalanceShift = invoiceBalanceShift.replace("@PayDetails", str(payDetails))
                else:
                    invoiceBalanceShift = invoiceBalanceShift.replace("@PayDetails", "No se realizaron Pagos\n")

                if "TotalItems" in turn:
                    typeItems = ""
                    for key, value in turn["TotalItems"].items():
                        key = key + ":"
                        key = key.ljust(22, " ")
                        typeItems += f"{key}$ {value}\n"
                    invoiceBalanceShift = invoiceBalanceShift.replace("@TypeItem", str(typeItems))
                else:
                    invoiceBalanceShift = invoiceBalanceShift.replace("@TypeItem", str("No se realizaron Pagos\n"))

                # !JSON SEND BALANCE SHIFT
                balanceShift = {}
                #* DATA OpenTurn
                balanceShift["Id_Shift"]        =  int(turn["Id_Shift"])
                balanceShift["InitialDate"]     =  turn["InitialDate"]
                balanceShift["InitInvoice"]     =  int(turn["InitInvoice"])
                balanceShift["InvoiceCount"]    =  turn["TotalInvoices"]
                balanceShift["InitialCash"]     =  turn["InitialCash"]
                balanceShift["FailReturn"]      =  turn["FailReturn"]
                balanceShift["MethodsPay"]      =  turn["MethodsPay"]
                balanceShift["InternalControl"] =  totalCash
                balanceShift["InvoiceTotal"]    =  turn["TotalwhitTaxes"]
                balanceShift["Receipt"]         =  str(invoiceBalanceShift)

                retorno = True
                message = "Balance del turno generado"
                logging.info(invoiceBalanceShift)

        except Exception as e:
            currentShift     = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error al generar balance: {currentShift}")
            message      = "Balance del turno no fue generado"
            balanceShift = ""

        finally :
            logging.info(f"Respuesta del balance turno: {message}")
            return retorno,balanceShift

    def statusTurn(self, content:dict):

        if not content: content =  {"Id_People": 0 , "CurrentCash": 0}

        try:
            logging.info("-----------------------------------------------------------------------")
            logging.info("                           Estatus del turno                           ")
            logging.info("-----------------------------------------------------------------------")

            #*get Data from "Turn"
            with open(self.controlShift) as dataTurn: turn = json.load(dataTurn)
            dataTurn.close()

            if turn["Status"] == 1:
                message = "EL TURNO YA FUE CERRADO"
                retorno = False
                invoiceStatusShift = ""
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                turn["Id_PeopleClosed"] = content["Id_People"]
                turn["FinishInvoice"]   = self.resolution["actualIndexResolution"]
                totalCash               = turn["CurrentCash"] + turn["StackControl"]

                with open(self.controlShift, 'w', encoding='utf-8') as file: json.dump(turn, file, indent=2)
                file.close()

                id_shift = str(turn['Id_Shift'])

                # !Generate Invoice StatusShift
                """
                @Empresa\n@Direccion\n@Telefono\n
                NIT: @Nit\n\n\n
                --------------------------------------------\n
                @DataAux\n
                --------------------------------------------\n
                ID Turno:             @IDTurno\n
                ID Apertura:          @IDApertura\n
                ID Cierre:            @IDCierre\n
                --------------------------------------------\n
                Fecha Apertura:       @FechaApertura\n
                Fecha Cierre:         @FechaCierre\n\n
                --------------------------------------------\n
                Factura Inicio:       @FacturaInicio\n
                Factura Final:        @FacturaFinal\n
                Total Facturas:       @TotalFacturas\n
                --------------------------------------------\n
                Base(Efectivo):       @Moneda @MontoInicial\n
                Recargas:             @Moneda @Recargas\n
                Retiros:              @Moneda @Vaciados\n
                Fallos al devolver:   @Moneda @FallosAlDevolver\n
                Efectivo Facturado:   @Moneda @Cash\n
                Efectivo Total:       @Moneda @ControlInterno\n
                --------------------------------------------\n
                Detalle de Pagos\n
                --------------------------------------------\n
                @PayDetails
                Total Facturado:      @Moneda @Total\n
                --------------------------------------------\n
                Detalle de Productos Facturados\n
                --------------------------------------------\n
                @TypeItem
                Total Facturado:      @Moneda @Total\n
                """
                templateInvoice = "@Empresa\n@Direccion\n@Telefono\nNIT: @Nit\n\n\n--------------------------------------------\n@DataAux\n--------------------------------------------\nID Turno:             @IDTurno\nID Apertura:          @IDApertura\nID Cierre:            @IDCierre\n--------------------------------------------\nFecha Apertura:       @FechaApertura\nFecha Cierre:         @FechaCierre\n\n--------------------------------------------\nFactura Inicio:       @FacturaInicio\nFactura Final:        @FacturaFinal\nTotal Facturas:       @TotalFacturas\n--------------------------------------------\nBase(Efectivo):       @Moneda @MontoInicial\nRecargas:             @Moneda @Recargas\nRetiros:              @Moneda @Vaciados\nFallos al devolver:   @Moneda @FallosAlDevolver\nEfectivo Facturado:   @Moneda @Cash\n                    ------------------------\n\nEfectivo Total:       @Moneda @ControlInterno\n--------------------------------------------\nDetalle de Pagos\n--------------------------------------------\n@PayDetailsTotal Facturado:      @Moneda @Total\n--------------------------------------------\nDetalle de Productos Facturados\n--------------------------------------------\n@TypeItem                    ------------------------\n\nTotal Facturado:      @Moneda @Total\n\n\n\n"
                enterprise = self.dataConfig["template_invoice"]

                invoiceStatusShift = templateInvoice
                invoiceStatusShift = invoiceStatusShift.replace("@Empresa", enterprise["enterprise"])
                invoiceStatusShift = invoiceStatusShift.replace("@Direccion", enterprise["address"])
                invoiceStatusShift = invoiceStatusShift.replace("@Telefono", enterprise["cellphone"])
                invoiceStatusShift = invoiceStatusShift.replace("@Nit", enterprise["nit"])

                invoiceStatusShift = invoiceStatusShift.replace("@DataAux", "Factura Cierre de Turno")

                invoiceStatusShift = invoiceStatusShift.replace("@IDTurno", str(turn["Id_Shift"]))
                invoiceStatusShift = invoiceStatusShift.replace("@IDApertura", str(turn["Id_PeopleOpening"]))
                invoiceStatusShift = invoiceStatusShift.replace("@IDCierre", str(turn["Id_PeopleClosed"]))

                invoiceStatusShift = invoiceStatusShift.replace("@FechaApertura", str(turn["InitialDate"]))
                invoiceStatusShift = invoiceStatusShift.replace("@FechaCierre", str(turn["FinalDate"]))

                invoiceStatusShift = invoiceStatusShift.replace("@FacturaInicio", str(turn["InitInvoice"]))
                invoiceStatusShift = invoiceStatusShift.replace("@FacturaFinal", str(turn["FinishInvoice"]))
                invoiceStatusShift = invoiceStatusShift.replace("@TotalFacturas", str(turn["TotalInvoices"]))

                invoiceStatusShift = invoiceStatusShift.replace("@Moneda", str(self.currency_symbol))
                invoiceStatusShift = invoiceStatusShift.replace("@MontoInicial", str(round(turn["InitialCash"])))
                invoiceStatusShift = invoiceStatusShift.replace("@Recargas", str(round(turn["Recharge"])))
                invoiceStatusShift = invoiceStatusShift.replace("@Vaciados", str(round(turn["Emptied"])))
                invoiceStatusShift = invoiceStatusShift.replace("@FallosAlDevolver", str(round(turn["FailReturn"])))
                #invoiceStatusShift = invoiceStatusShift.replace("@Cash", str(round(turn["MethodsPay"])))
                invoiceStatusShift = invoiceStatusShift.replace("@ControlInterno", str(round(totalCash)))
                invoiceStatusShift = invoiceStatusShift.replace("@Total", str(round(turn["TotalwhitTaxes"])))

                if "Efectivo" in turn["MethodsPay"]:
                    invoiceStatusShift = invoiceStatusShift.replace("@Cash", str(round(turn["MethodsPay"]["Efectivo"])))
                else:
                    invoiceStatusShift = invoiceStatusShift.replace("@Cash", str(0))
                if turn["MethodsPay"]:
                    payDetails = ""
                    for key, value in turn["MethodsPay"].items():
                        key = key + ":"
                        key = key.ljust(22, " ")
                        payDetails += f"{key}$ {value}\n"
                    invoiceStatusShift = invoiceStatusShift.replace("@PayDetails", str(payDetails))
                else:
                    invoiceStatusShift = invoiceStatusShift.replace("@PayDetails", "No se realizaron Pagos\n")

                if "TotalItems" in turn:
                    typeItems = ""
                    for key, value in turn["TotalItems"].items():
                        key = key + ":"
                        key = key.ljust(22, " ")
                        typeItems += f"{key}$ {value}\n"
                    invoiceStatusShift = invoiceStatusShift.replace("@TypeItem", str(typeItems))
                else:
                    invoiceStatusShift = invoiceStatusShift.replace("@TypeItem", str("No se realizaron Pagos\n"))

                retorno = True

                logging.info(f"Respuesta estatus turno: {message}")
                logging.info(invoiceStatusShift)

                Invoice_bytes  = invoiceStatusShift.encode()
                Invoice_Base64 = base64.b64encode(Invoice_bytes)

        except Exception as e:
            logging.error(f"Error al generar estatus turno: {e}")
            retorno = False
            invoiceStatusShift = ""
            return {"Error" : str(e)}
        finally:
            return retorno,invoiceStatusShift

    def addInvoiceTurn(self, dataShift:dict):

        url_shiftResult = self.dataPath + "shiftControl/shiftResults/"
        idTransaction = dataShift["epoch"]
        dataShift.pop("epoch")

        totalItems = dataShift["TotalItems"]
        dataShift.pop("TotalItems")

        shiftPackage = url_shiftResult + f"{dataShift['IdShift']}/"
        nameInvoice  = f"{dataShift['Prefix']}{dataShift['IdInvoice']}"
        with open(shiftPackage + nameInvoice + ".json", "w") as backupShift: json.dump(dataShift, backupShift, indent = 4)
        backupShift.close()

        #Insert Invoice in "package billings"

        nameInvoice  = f"billingResult-{idTransaction}"
        with open(self.saveBilling + nameInvoice + ".json", "w") as uploadShift: json.dump(dataShift, uploadShift, indent = 4)
        uploadShift.close()

        #get Data from "Turn"
        with open(self.controlShift) as dataTurn: turn = json.load(dataTurn)
        dataTurn.close()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update JSON ControlShift
        turn["TotalInvoices"]     += 1
        turn["TotalTaxes"]        += round(dataShift["TotalTaxes"],2)
        turn["TotalwhitOutTaxes"] += round(dataShift["TotalWithoutTaxes"],2)
        turn["TotalwhitTaxes"]    += round(dataShift["Total"],2)
        turn["LastInsert"]         = str(timestamp)

        if dataShift["PaymentMethod"] == 0:
            if "Efectivo" in turn["MethodsPay"]:
                turn["MethodsPay"]["Efectivo"] += round(dataShift["Total"],2)
                turn["InternalControl"]    += round(dataShift["Total"],2)
            else:
                turn["MethodsPay"]["Efectivo"] = 0
                turn["MethodsPay"]["Efectivo"] += round(dataShift["Total"],2)
                turn["InternalControl"]    += round(dataShift["Total"],2)

        if dataShift["PaymentMethod"] == 1:
            if "Tarjeta" in turn["MethodsPay"]:
                turn["MethodsPay"]["Tarjeta"] += round(dataShift["Total"],2)
            else:
                turn["MethodsPay"]["Tarjeta"] = 0
                turn["MethodsPay"]["Tarjeta"] += round(dataShift["Total"],2)

        if dataShift["PaymentMethod"] == 2:
            if "Magnetica" in turn["MethodsPay"]:
                turn["MethodsPay"]["Magnetica"] += round(dataShift["Total"],2)
            else:
                turn["MethodsPay"]["Magnetica"]  = 0
                turn["MethodsPay"]["Magnetica"] += round(dataShift["Total"],2)

        if dataShift["PaymentMethod"] == 3:
            if "Flypass" in turn["MethodsPay"]:
                turn["MethodsPay"]["Flypass"] += round(dataShift["Total"],2)
            else:
                turn["MethodsPay"]["Flypass"]  = 0
                turn["MethodsPay"]["Flypass"] += round(dataShift["Total"],2)

        if dataShift["PaymentMethod"] == 4:
            if "Nequi" in turn["MethodsPay"]:
                turn["MethodsPay"]["Nequi"] += round(dataShift["Total"],2)
            else:
                turn["MethodsPay"]["Nequi"]  = 0
                turn["MethodsPay"]["Nequi"] += round(dataShift["Total"],2)

        if dataShift["PaymentMethod"] == 5:
            if "Bancolombia" in turn["MethodsPay"]:
                turn["MethodsPay"]["Bancolombia"] += round(dataShift["Total"],2)
            else:
                turn["MethodsPay"]["Bancolombia"]  = 0
                turn["MethodsPay"]["Bancolombia"] += round(dataShift["Total"],2)

        if dataShift["PaymentMethod"] == 6:
            if "Rappi" in turn["MethodsPay"]:
                turn["MethodsPay"]["Rappi"] += round(dataShift["Total"],2)
            else:
                turn["MethodsPay"]["Rappi"]  = 0
                turn["MethodsPay"]["Rappi"] += round(dataShift["Total"],2)

        if dataShift["PaymentMethod"] == 7:
            if "Transferencia" in turn["MethodsPay"]:
                turn["MethodsPay"]["Transferencia"] += round(dataShift["Total"],2)
            else:
                turn["MethodsPay"]["Transferencia"]  = 0
                turn["MethodsPay"]["Transferencia"] += round(dataShift["Total"],2)

        if totalItems:
            for key, value in totalItems.items():
                if "Carro" in totalItems:
                    print("entro aqui",totalItems)
                    if "Carro" in turn["TotalItems"]: turn["TotalItems"]["Carro"] += round(value)
                    else:
                        turn["TotalItems"]["Carro"] = 0
                        turn["TotalItems"]["Carro"] += round(value)
                elif "Moto" in totalItems:
                    print("entro aqui",totalItems)
                    if "Moto" in turn["TotalItems"]: turn["TotalItems"]["Moto"] += round(value)
                    else:
                        turn["TotalItems"]["Moto"] = 0
                        turn["TotalItems"]["Moto"] += round(value)
                elif "Placa" in totalItems:
                    print("entro aqui",totalItems)
                    if "Placa" in turn["TotalItems"]: turn["TotalItems"]["Placa"] += round(value)
                    else:
                        turn["TotalItems"]["Placa"] = 0
                        turn["TotalItems"]["Placa"] += round(value)

        if "notDispense" in dataShift["PaymentDetails"] : turn["FailReturn"] += dataShift["PaymentDetails"]["notDispense"]

        with open(self.controlShift ,'w') as update_turn: json.dump(turn, update_turn, indent=4)
        update_turn.close()

    def generateTemplateTurn(self):

        self.getSettings()
        # !JSON CONTROL INTERNAL SHIFTS

        timestamp    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        currentShift = {}
        # DATA SHIFT
        currentShift["Id_Shift"]         = 0
        currentShift["Id_Device"]        = int(self.idDevice)
        currentShift["InitialDate"]      = str(timestamp)
        currentShift["FinalDate"]        = ""
        currentShift["Status"]           = 0

        # DATA OPEN SHIFT
        currentShift["InitInvoice"]      = self.resolution["actualIndexResolution"]
        currentShift["FinishInvoice"]    = 0
        currentShift["Id_PeopleOpening"] = 0
        currentShift["InitialCash"]      = 0
        currentShift["InternalControl"]  = 0
        currentShift["Diference"]        = 0


        #DATA CLOSE SHIFT
        currentShift["Id_PeopleClosed"]  = 0
        currentShift["FinalCash"]        = 0
        currentShift["MethodsPay"]       = {}

        #TOTAL INFO SHIFT
        currentShift["TotalInvoices"]      = 0
        currentShift["TotalTaxes"]         = 0
        currentShift["TotalwhitTaxes"]     = 0
        currentShift["TotalwhitOutTaxes"]  = 0
        currentShift["FailReturn"]         = 0
        currentShift["Emptied"]            = 0
        currentShift["Recharge"]           = 0
        currentShift["StackControl"]       = 0
        currentShift["LastInsert"]         = str(timestamp)
        currentShift["TotalItems"]         = {}

        currentShift["NextIdShift"]               = 1

        return currentShift

    #GESTOR RESOLUCION
    def checkResolution(self)-> bool:

        indexResolution      = self.resolution["actualIndexResolution"]
        dateNow              = datetime.now()
        initResolution       = self.resolution["startNumber"]
        finishResolution     = self.resolution["endNumber"]
        initDateResolution   = self.resolution["startDate"]
        finishDateResolution = self.resolution["endDate"]

        initDateResolution   = datetime.strptime(initDateResolution, '%Y-%m-%d')
        finishDateResolution = datetime.strptime(finishDateResolution, '%Y-%m-%d')

        dateNow     = datetime.strftime(dateNow,'%Y-%m-%d')
        dateNow     = datetime.strptime(dateNow,'%Y-%m-%d')
        dateInvoice = dateNow
        infoMessage = ""

        check = False
        if dateInvoice >= initDateResolution and dateInvoice <= finishDateResolution :
            logging.info("FACTURA DENTRO DE FECHAS DE RESOLUCION")
            if indexResolution >= initResolution and indexResolution <= finishResolution:
                logging.info(f"FACTURA {indexResolution} de {finishResolution}")

                alertResolution = (indexResolution * 100) / finishResolution

                if alertResolution == 90: logging.info("Consecutivos de la resolucion al 10% de finalizar")

                check = True
            else:
                logging.info("RESOLUCION SIN CONSECUTIVOS")
                infoMessage = "RESOLUCION SIN CONSECUTIVOS"
                check = False
        else:
            logging.info("FACTURA FUERA DE FECHAS DE RESOLUCION")
            infoMessage = "FACTURA FUERA DE FECHAS DE RESOLUCION"
            check       = False

        return check, infoMessage

    def updateResolution (self)-> None:

        try:
            url_ControlShift  = f"{self.dataPath}shiftControl/"
            if not os.path.isdir(url_ControlShift): os.makedirs(url_ControlShift)

            if os.path.exists(self.nextInvoice):

                # *Get Data Resolution
                with open(self.nextInvoice, "r") as file: self.resolution = json.load(file)
                file.close()

            else:
                logging.info(" ----------------> No se encontro Resolucion Local")
                logging.info(" ----------------> Creando Resolucion Local ...")

                nextinvoice = {
                                "prefijo": "Empty",
                                "numResolution": "0000",
                                "startNumber": 1,
                                "endNumber": 1,
                                "orderToUse": 1,
                                "startDate": "2000-01-01",
                                "endDate": "2000-01-01",
                                "actualIndexResolution": 0
                                }

                with open(self.nextInvoice, "w") as createResolution: json.dump(nextinvoice, createResolution, indent = 4)
                createResolution.close()

                with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                file.close()

            if self.resolution:
                if self.resolution.get("prefijo") == "Empty" or self.resolution.get("actualIndexResolution") == 0:

                    self.dataGovernor = self.configService()

                    if self.dataGovernor:
                         # * Update Local Resolution
                        nextinvoice = {}
                        nextinvoice['prefijo']       = self.dataGovernor["Prefijo"]
                        nextinvoice['numResolution'] = self.dataGovernor["ResolutionNumber"]
                        nextinvoice['startNumber']   = self.dataGovernor["BillingIniNumber"]
                        nextinvoice['endNumber']     = self.dataGovernor["BillingEndNumber"]
                        nextinvoice['startDate']     = self.dataGovernor["DateIniResolution"]
                        nextinvoice['endDate']       = self.dataGovernor["DateEndResolution"]
                        nextinvoice["actualIndexResolution"] = self.dataGovernor["BillingNumber"] + 1

                        with open(self.nextInvoice, "w") as updateResolution: json.dump(nextinvoice, updateResolution, indent = 4)
                        updateResolution.close()

                        logging.info((f" -------------> Resolucion actualizada"))
                        with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                        file.close()
                    else:
                        logging.info(f" --------------> Ha ocurrido un error al Actualizar la resolucion")
                        logging.info(f" --------------> Se Usara resolucion local ")

                        with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                        file.close()
                else:
                    with open(self.nextInvoice,'r') as file: self.resolution = json.load(file)
                    file.close()

        except Exception as e:
            currentShift     = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error Actualizando Resolucion: {currentShift}")

    def configService(self) -> None:

        try:

            def on_message(client, topic, id, mcmd, session, raw1):
                logging.info("----------------------------")
                logging.info(f"ID      : {id}")
                logging.info(f"MCMD    : {mcmd}")
                # logging.info(f"RESPONSE: {raw1}")
                logging.info("----------------------------")

                self.responseData = raw1

            self.responseData = None
            credential = {"id": self.idDevice }
            credential = json.dumps(credential)
            command    = "GETINVOICESTATUS"
            session    = self._mqtt.newsession(None)

            self._mqtt._callback[session] = on_message
            self._mqtt.sendcommand(self.topic,command,credential,session)

            i = 0
            while not self.responseData:
                i += 1
                time.sleep(1)
                if i == 10 :
                    logging.info("sin respuesta")
                    break

            if self.responseData:
                settings = self.responseData.decode("utf-8")
                return eval(settings)

        except Exception as e:
            error = str(e) + ": " + traceback.format_exc()
            logging.error(f"Error Configurando Servicio Facturacion: {error}")

    # RECARGAS Y VACIADOS
    def moneyManager(self, dataInvoice:dict)-> str:
        # TEMPLATE INVOICE
        """
            --------------------------------------------\n
                @Tipo\n
            --------------------------------------------\n
                Usuario: @Usuario\n
                ID: @IdVaciado\n
            --------------------------------------------\n
                Cantidad           Denominacion         \n
            --------------------------------------------\n
                @DatosFactura\n\n
                                -------------------\n
                Valor :              $@Valor\n
            --------------------------------------------\n
                Motivo: @Motivo\n
                Fecha:  @Fecha\n
            --------------------------------------------\n
        """
        try:
            checkshift = self.checkTurn()

            if checkshift:
                templateInvoice = "--------------------------------------------\n    @Tipo\n--------------------------------------------\n    Usuario: @Usuario\n    ID: @IdVaciado\n--------------------------------------------\n    Cantidad           Denominacion         \n--------------------------------------------\n@DatosFactura\n                    -------------------\n    Valor :             $@Valor\n--------------------------------------------\n    Motivo: @Motivo\n    Fecha:  @Fecha\n--------------------------------------------\n"

                #* Get DATATURN
                # url_ControlShift  = f"{self.dataPath}shiftControl/controlShift.json"
                with open(self.controlShift) as file: turn = json.load(file)
                file.close()
                status = True
                invoice = ""
                if dataInvoice["typeInvoice"]   == 1:
                    logging.info("---> Realizando Recarga")
                    typeInvoice      = "Recarga"
                    turn["Recharge"] += dataInvoice['total']
                    turn["InternalControl"] += dataInvoice['total']

                elif dataInvoice["typeInvoice"] == 2:
                    logging.info("---> Realizando Vaciado")
                    typeInvoice     = "Vaciado"
                    turn["Emptied"] += dataInvoice['total']
                    turn["InternalControl"] -= dataInvoice['total']

                else:
                    logging.info("---> No existe el tipo de factura seleccionada")
                    status = False

                idRecharge = int(datetime.timestamp(datetime.now()))
                dateInvoce = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                infoInvoice =""
                if status:
                    for money in dataInvoice["money"]:

                        denomination = int(money["Denominacion"])
                        amount       = str(money["Cantidad"])

                        if len(amount) == 1:
                            infoInvoice += f"       {amount}{('$'+str(denomination)).rjust(21)}\n"
                        if len(amount) == 2:
                            infoInvoice += f"       {amount}{('$'+str(denomination)).rjust(20)}\n"

                        if len(amount) == 3:
                            infoInvoice += f"       {amount}{('$'+str(denomination)).rjust(19)}\n"

                    invoice = templateInvoice
                    invoice = invoice.replace("@Tipo", f"{typeInvoice}")
                    invoice = invoice.replace("@Usuario", str(self.idDevice))
                    invoice = invoice.replace("@IdVaciado", str(idRecharge))
                    invoice = invoice.replace("@DatosFactura", infoInvoice)
                    invoice = invoice.replace("@Valor", f"{dataInvoice['total']}")
                    invoice = invoice.replace("@Motivo", dataInvoice["textInvoice"])
                    invoice = invoice.replace("@Fecha", dateInvoce)

                    #* UPDATE DATA TURN
                    with open(self.controlShift,'w', encoding='utf-8') as file: json.dump(turn, file, indent=4)
                    file.close()

                    # !JSON SEND MoneyManager
                    invoiceManager = {}
                    #* DATA MoneyManager
                    dateBilling    = datetime.now()
                    epoch          = int(datetime.timestamp(dateBilling)*1)

                    invoiceManager = {}
                    invoiceManager["JsonType"] =  4
                    invoiceManager["Administrativa"]   = {}
                    invoiceManager["Administrativa"]["Id_Device"]              =  int(self.idDevice)
                    invoiceManager["Administrativa"]["Id_BillTransaction"]     =  f"{self.idDevice}{epoch}"
                    invoiceManager["Administrativa"]["Id_BillTransactionType"] =  dataInvoice["typeInvoice"]
                    invoiceManager["Administrativa"]["Id_Shift"]               =  int(turn["Id_Shift"])
                    invoiceManager["Administrativa"]["Id_People"]              =  turn["Id_PeopleOpening"]
                    invoiceManager["Administrativa"]["Date"]                   =  str(dateInvoce)
                    invoiceManager["Administrativa"]["Value"]                  =  dataInvoice['total']
                    invoiceManager["Administrativa"]["Text"]                   =  str(dataInvoice["textInvoice"])


                    nameInvoice = f"shiftResult-{int(time.time()*1000)}"
                    with open(self.saveBilling + str(nameInvoice) + '.json','w') as sendInvoice: json.dump(invoiceManager, sendInvoice, indent= 4)
                    sendInvoice.close()

                    invoiceManager["Receipt"] =  str(invoice)


            else:
                logging.info("---> El turno no fue encontrado")
                status         = False
                invoiceManager = ""

        except Exception as e:
            error   = str(e) + ": " + traceback.format_exc()
            logging.error(f"Ha ocurrido un error en moneyManager: -->{error}")
            status = False

        finally: return status, invoiceManager

    def stackControl(self, totalAmount, type) -> None:

        try:
            # url_ControlShift  = f"{self.dataPath}shiftControl/controlShift.json"
            with open(self.controlShift) as file: turn = json.load(file)
            file.close()

            if type == 1:
                turn["StackControl"] += totalAmount
                logging.info(f"SE ALMACENO EN STACK: ${totalAmount}")
            if type == 2:
                turn["StackControl"] -= totalAmount
                logging.info(f"SE RETIRO DEL STACK: ${totalAmount}")
            if type == 2:
                turn["StackControl"]
                logging.info(f"Total en STACK: ${turn['StackControl']}")

            with open(self.controlShift,'w', encoding='utf-8') as file:
                json.dump(turn, file, indent=4)
            file.close()

            return turn["StackControl"]

        except Exception as e:
            logging.error(f"Ha Ocurrido un error --> StackControl {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,  format='%(levelname)s::%(asctime)s::%(module)s::%(funcName)s::line %(lineno)d %(message)s')

    # Test
    dataPath = "C:/mascotas/kiosTag/copia/python/kiosk_tag/data/"

    dataConfig = {
                    "Currency_symbol": "$",
                    "adjustment": 100,
                    "template_invoice":{
                        "enterprise": "BOREALIX SAS.",
                        "nit": "901131640",
                        "address": "Calle 128 # 50 - 52, Bogota D.C.",
                        "cellphone":"(+57) 3167801948",
                        "footer": "NO SOMOS AUTORETENEDORES\nNO SOMOS GRANDES CONTRIBUYENTES\nREGIMEN COMUN\n\nGARANTIA DE 3 MESES POR FALLAS O DEFECTOS DE\nFABRICACION ENTREGADA POR EL PROVEEDOR\n"
                    }
                }

    settings = 1

    dataResolution = [
                        {
                            "BillinPrefix": "PET99",
                            "BillinResolution": "000231",
                            "BillinNumbreStart": 100,
                            "BillinNumberEnd": 500,
                            "BillinDateStart": "2022-12-01",
                            "BillinDateEnd": "2023-12-31"
                        }
                    ]
    saveBilling    = "C:/mascotas/kiosTag/copia/python/kiosk_tag/data/transactions/"
    dataOpen       = {"Id_People": 1 , "InitialCash": 0}
    dataClose      = {"Id_People": 1 , "FinalCash": 0}
    dataInvoice    = {
                    "isElectronic": False,
                    "Details": {
                        "Nombre":"placa prueba",
                        "Telefono":310235478,
                        "email": "NOEMAIL"
                    },
                    "Tax": [
                            {
                            "Id_Tax": 2,
                            "TaxValue": 19
                            }
                    ],
                    "items":[
                        {
                            "Id_Product": 11,
                            "description":"hueso grande",
                            "Total": 16000,
                            "taxes": [2],
                            "include":True,
                        }
                    ],
                    "PaymentMethod": 1,
                    "PaymentDetails":{
                                "valuePaid": 16000,
                                "change": 0,
                                "notDispense": 0
                    },
                    "Note": {
                        "Nombre":"nombretest",
                        "Telefono": 31254896,
                        "email": "NOEMAIL"
                    },
                }

    # Create INSTANCE
    invoicing = Service_invoicing()
    invoicing.start(dataPath,dataConfig, settings, dataResolution, saveBilling)
    invoicing.openTurn(dataOpen)

    for i in range(1,5):
        invoicing.invoice(dataInvoice)
        invoicing.checkTurn()
        sleep(4)

    invoicing.closeTurn(dataClose)
    pass