# Classes and Objects
## Class
A class is a blueprint that defines the data and behaviour shared by a group of objects. In Java, a class contains fields that store state and methods that define behaviour. A class does not occupy memory for its fields until an object is created from it.
## Object
An object is an instance of a class that has its own state, behaviour and identity. Objects are created in Java using the new keyword, which allocates memory on the heap and returns a reference. Each object stores its own copy of the instance variables declared in its class.

# Constructors
## Constructor
A constructor is a special method that initializes a newly created object and has the same name as its class. A constructor has no return type, not even void. If a programmer does not write any constructor, the Java compiler provides a default constructor with no parameters. Constructor overloading allows a class to have more than one constructor with different parameter lists.
## this keyword
The this keyword refers to the current object inside an instance method or constructor. The this keyword is commonly used to distinguish instance variables from parameters that have the same name.

# Inheritance
## Inheritance
Inheritance is the mechanism by which one class acquires the fields and methods of another class. In Java, inheritance is declared using the extends keyword, and the class that inherits is called the subclass. Inheritance promotes code reuse because common behaviour is written once in the superclass. Java supports single, multilevel and hierarchical inheritance with classes but does not support multiple inheritance with classes.
## super keyword
The super keyword refers to the immediate parent class of an object. The super keyword can be used to call the parent class constructor, and such a call must be the first statement in the subclass constructor.

# Polymorphism
## Method Overloading
Method overloading means defining several methods in the same class with the same name but different parameter lists. Method overloading is resolved by the compiler, so it is called compile-time polymorphism.
## Method Overriding
Method overriding occurs when a subclass provides its own implementation of a method that is already defined in its superclass. Method overriding is resolved at run time based on the actual object type, so it is called run-time polymorphism. An overriding method must have the same name, the same parameters and a compatible return type.
## Polymorphism
Polymorphism is the ability of a single interface or method name to take many forms. Polymorphism allows a superclass reference to refer to a subclass object and invoke the subclass version of an overridden method.

# Abstraction
## Abstract Class
An abstract class is a class declared with the abstract keyword that cannot be instantiated. An abstract class can contain both abstract methods without a body and concrete methods with a body. A subclass of an abstract class must implement all its abstract methods or must itself be declared abstract.
## Interface
An interface is a reference type that specifies a set of methods a class must implement. A class implements an interface using the implements keyword, and a class can implement multiple interfaces. Interfaces allow Java to achieve a form of multiple inheritance of type without the problems of multiple inheritance of state.

# Encapsulation
## Encapsulation
Encapsulation is the bundling of data and the methods that operate on that data into a single unit while hiding the internal details. Encapsulation is achieved in Java by declaring fields private and providing public getter and setter methods. Encapsulation protects an object from invalid state because all changes pass through controlled methods.
## Access Modifier
An access modifier controls the visibility of a class, field or method. Java provides four access levels: private, default, protected and public. A private member is visible only inside its own class, while a public member is visible everywhere.

# Exception Handling
## Exception
An exception is an event that disrupts the normal flow of a program during execution. Checked exceptions are verified by the compiler, while unchecked exceptions are subclasses of RuntimeException and are not checked at compile time.
## try-catch
A try-catch block is used to handle exceptions so that a program can continue running. The code that may throw an exception is placed inside the try block, and the handling code is placed inside the catch block. A finally block always executes whether or not an exception is thrown, and it is often used to release resources.
