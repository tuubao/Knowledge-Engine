package com.kb.engine.mapper;

import com.kb.engine.entity.KbTaskNode;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

import java.util.List;

@Mapper
public interface KbTaskNodeMapper {

    int insert(KbTaskNode node);

    int update(KbTaskNode node);

    List<KbTaskNode> listByTaskId(@Param("taskId") String taskId);

    int deleteByTaskId(@Param("taskId") String taskId);
}
