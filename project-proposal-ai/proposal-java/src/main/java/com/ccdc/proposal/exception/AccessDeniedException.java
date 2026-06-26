package com.ccdc.proposal.exception;

/**
 * [MVP] 权限异常（修复 P0-7：权限不足返回 403 而非 400）
 */
public class AccessDeniedException extends RuntimeException {
    public AccessDeniedException(String message) {
        super(message);
    }
}
