# class Singleton:
#     _instance = None

#     def __new__(cls):
#         if cls._instance is None:
#             cls._instance = super().__new__(cls)
#         return cls._instance
    

# a = Singleton()
# b = Singleton()
# print(a is b)


# def fibonacci_generator():
#     a, b = 0, 1
#     while True:
#         yield a
#         a, b = b, a + b

# def print_fibonnaci(n):
#     gen = fibonacci_generator()
#     for _ in range(n):
#         print(next(gen), end=" ")

# print_fibonnaci(10)

class A:
    def greet(self):
        print("Hello from A")

class B(A):
    def greet(self):
        super().greet()
        print("Hello from B")

class C(A):
    def greet(self):
        super().greet()
        print("Hello from C")

class D(B, C):
    def greet(self):
        super().greet()
        print("Hello from D")

d = D()
d.greet()
print(D.__mro__)


#Adapter

class PaymentProcessor:
    def pay(self, amount):
        raise NotImplementedError("Subclasses must implement the pay method")


# def reverse_array(arr):
#     left = 0
#     right = len(arr) -1
    
#     while left < right:
#         arr[left], arr[right] = arr[right], arr[left]
#         left += 1
#         right -= 1
        
#     return arr
    
# arr = [1,2,3,4,5,6]
# reverse_array(arr)
# print(arr)

# class Queue: #FIFO
#     def __init__(self):
#         self.items = []
    
#     def enqueue(self, item):
#         self.items.append(item)

#     def dequeue(self):
#         if not self.is_empty():
#             return self.items.pop(0)

#     def is_empty(self):
#         return len(self.items) == 0

#     def size(self):
#         return len(self.items)

#     def front(self):
#         if not self.is_empty():
#             return self.items[0]

#     def rear(self):
#         if not self.is_empty():
#             return self.items[-1]

#     def display(self):
#         print(self.items)


# q = Queue()
# q.enqueue(1)
# q.enqueue(2)
# q.enqueue(3)
# q.enqueue(4)
# q.enqueue(5)
# q.display()
# q.dequeue()
# q.display()
# print(q.front())
# print(q.rear())

# class Stack: #LIFO
#     def __init__(self):
#         self.items = []

#     def push(self, item):
#         self.items.append(item)  # Add to the top

#     def pop(self):
#         if self.is_empty():
#             raise IndexError("Stack is empty")
#         return self.items.pop()  # Remove from the top

#     def peek(self):
#         if self.is_empty():
#             raise IndexError("Stack is empty")
#         return self.items[-1]

#     def is_empty(self):
#         return len(self.items) == 0

#     def size(self):
#         return len(self.items)


# class ListNode:
#     def __init__(self, value=0, next=None):
#         self.value = value
#         self.next = next


# def reverse_list(head):
#     prev = None
#     current = head

#     while current:
#         next_node = current.next #save next node
#         current.next = prev #reverse the pointer
#         prev = current #move prev frowrd
#         current = next_node
    
#     return prev

# def print_list(node):
#     while node:
#         print(node.value, end=" -> ")
#         node = node.next
#     print("None")

# #Creating linked list
# head = ListNode(1, ListNode(2, ListNode(3, ListNode(4, ListNode(5)))))
# print("Original Linked List:")
# print_list(head)

# reverserd_head = reverse_list(head)
# print("Reversed Linked List:")
# print_list(reverserd_head)


# def simple_cache(func):
#     cache = {}

#     def wrapper(*args):
#         if args in cache:
#             return cache[args]
#         result = func(*args)
#         cache[args] = result
#         return result
#     return wrapper

# @simple_cache
# def slow_add(a, b):
#     print(f"Computing {a} + {b}")
#     return a + b

# print(slow_add(1, 2))
# print(slow_add(1, 2))

# from functools import lru_cache
# @lru_cache(maxsize=None)
# def slow_add(a, b):
#     print(f"Computing {a} + {b}")
#     return a + b
# print(slow_add(1, 2))
# print(slow_add(1, 2))
# print(slow_add(5, 2))


