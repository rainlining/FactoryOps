package com.factoryops.business.batch.domain;
public record HoldCommand(HoldReasonCode reasonCode,String reasonDetail,String inspectionId,String resultId) {
 public HoldCommand { if(reasonCode==null)throw new IllegalArgumentException("reason_code required");reasonDetail=detail(reasonDetail);boolean evidence=inspectionId!=null&&resultId!=null;if(reasonCode==HoldReasonCode.QUALITY_ANOMALY&&!evidence)throw new IllegalArgumentException("quality evidence required");if(reasonCode!=HoldReasonCode.QUALITY_ANOMALY&&(inspectionId!=null||resultId!=null))throw new IllegalArgumentException("evidence forbidden"); }
 public static HoldCommand manual(HoldReasonCode code,String detail){return new HoldCommand(code,detail,null,null);}
 private static String detail(String value){if(value==null)return null;var v=value.trim();if(v.isEmpty()||v.length()>500)throw new IllegalArgumentException("invalid reason_detail");return v;}
}
