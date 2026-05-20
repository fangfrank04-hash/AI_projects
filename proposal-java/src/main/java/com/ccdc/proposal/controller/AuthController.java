package com.ccdc.proposal.controller;

import com.ccdc.proposal.dto.request.SsoLoginRequest;
import com.ccdc.proposal.security.TokenService;
import jakarta.annotation.Resource;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 认证接口（已有）
 * [MVP] 开发环境：简单 token 生成
 */
@RestController
@RequestMapping("/api/auth")
public class AuthController {

    @Resource
    private TokenService tokenService;

    /**
     * [MVP] 开发环境登录（简化版）
     * TODO: [V2] 生产环境集成SSO/LDAP
     */
    @PostMapping("/sso-login")
    public ResponseEntity<Map<String, Object>> ssoLogin(@RequestBody SsoLoginRequest request) {
        // [MVP] 开发环境：生成简单JWT
        String token = tokenService.generateToken("张三", "张三");
        return ResponseEntity.ok(Map.of(
                "token", token,
                "user", Map.of(
                        "userId", "张三",
                        "userName", "张三",
                        "dept", "技术部",
                        "roles", new String[]{"PM"}
                )
        ));
    }

    /**
     * [MVP] 获取测试token
     */
    @GetMapping("/test-token")
    public ResponseEntity<Map<String, String>> getTestToken() {
        String token = tokenService.generateToken("张三", "张三");
        return ResponseEntity.ok(Map.of("token", token));
    }
}
