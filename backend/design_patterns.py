
# #Adapter

# #Target interface - what client expects
# class PaymentProcessor:
#     def pay(self, amount):
#         raise NotImplementedError
    
# #Existing Incompatible class
# class OldPaymentGateway:
#     def make_payment(self, value):
#         print(f"[OldGateway] payment of {value} processed")

# #Adapter - bridges the gap

# class PaymentAdapter(PaymentProcessor):
#     def __init__(self, old_gateway):
#         self.old_gateway = old_gateway

#     def pay(self, amount):
#         self.old_gateway.make_payment(amount)


# # Client code
# def process_order(payment_processor: PaymentProcessor):
#     payment_processor.pay(500)


# old_gateway = OldPaymentGateway()
# adapter = PaymentAdapter(old_gateway)
# process_order(adapter)

from abc import ABC, abstractmethod
#Observer Interface
class Observer(ABC):
    @abstractmethod
    def update(self, price:float):
        pass
    
#Subject Interface
class Subject(ABC):
    @abstractmethod
    def attach(self, observer: Observer):
        pass
    
    @abstractmethod
    def detach(self, observer: Observer):
        pass
    
    @abstractmethod
    def notify(self):
        pass
    
#Concrete Subject 
class Stock(Subject):
    def __init__(self, name: str):
        self.name = name
        self._price = 0.0
        self._observers = []
        
    
    def attach(self, observer: Observer):
        self._observers.append(observer)
    
    def detach(self, observer: Observer):
        self._observers.remove(observer)
    
    def notify(self):
        for observer in self._observers:
            observer.update(self._price)
            
    def set_price(self, price : float):
        print(f"Stock {self.name} new price: {price}")
        self._price = price
        self.notify()
        
        

    
    
# Concrete Observer
class Trader(Observer):
    def __init__(self, name: str):
        self.name = name
    
    def update(self, price: float):
        print(f"{self.name} notified: Price changed to {price}")
        
stock = Stock("INFY")
trader1 = Trader("Ram")
trader2 = Trader("Laxman")

stock.attach(trader1)
stock.attach(trader2)
stock.set_price(100.0)
stock.set_price(110.0)
stock.detach(trader2)
stock.set_price(200.0)