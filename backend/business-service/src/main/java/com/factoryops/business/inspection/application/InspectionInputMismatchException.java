package com.factoryops.business.inspection.application;
public final class InspectionInputMismatchException extends RuntimeException { private final String path; public InspectionInputMismatchException(String path){super("result input does not match inspection input");this.path=path;} public String path(){return path;} }
