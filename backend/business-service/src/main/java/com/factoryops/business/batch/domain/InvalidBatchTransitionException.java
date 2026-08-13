package com.factoryops.business.batch.domain;
public class InvalidBatchTransitionException extends RuntimeException { public InvalidBatchTransitionException(){super("Batch transition is not allowed");} }
