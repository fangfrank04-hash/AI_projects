package com.ccdc.proposal.entity;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 职责项（name + checked），用于前端复选框交互
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class ResponsibilityItem {
    private String name;
    private boolean checked = true;
}
